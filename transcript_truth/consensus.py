"""Consensus across independent acoustic witnesses. Runs the panel (Whisper + Scribe +
Deepgram), aligns the two strong reads token-by-token, and reports: agreement % (locked,
no ear needed), and the disagreement spans (the short list to ear-check). Deepgram is a
tiebreaker vote. No single model decides — agreement IS the verification.
"""
import difflib
import os
import subprocess
import tempfile
from .verdict import _toks

# ----------------------------------------------------------------------------
# Language-aware roster consensus (multilingual; does NOT use the JP tokenizer).
# Witnesses are chosen PER LANGUAGE — a model that produces wrong-language output
# (e.g. Gemini -> Russian on Ukrainian, vanilla Whisper -> Latin) is excluded so it
# can't poison the vote. Rosters are ordered by measured reliability.
# ----------------------------------------------------------------------------
ROSTER = {
    "ja": ["deepgram", "scribe", "gemini", "hf"],   # JP: all four read it; Deepgram strongest backbone
    "ru": ["deepgram", "scribe", "hf", "gemini"],   # all usable; Deepgram strongest
    "uk": ["deepgram", "scribe"],                     # only these stay in Ukrainian; others drift
    "es": ["deepgram", "scribe", "hf", "gemini"],   # well-supported by all witnesses
    "en": ["deepgram", "scribe", "hf", "gemini"],
    "fr": ["deepgram", "scribe", "hf", "gemini"],   # Tier-1: well-supported by all witnesses
    "de": ["deepgram", "scribe", "hf", "gemini"],   # Tier-1
    "pt": ["deepgram", "scribe", "hf", "gemini"],   # Tier-1
    "tr": ["deepgram", "scribe", "hf", "gemini"],   # Tier-1
    "ko": ["deepgram", "scribe", "gemini", "hf"],   # Tier-2: Korean, all read it
    "vi": ["deepgram", "scribe", "gemini", "hf"],   # Tier-2: Vietnamese
    "ar": ["deepgram", "scribe", "gemini", "hf"],   # Tier-3: witness quality not yet battery-validated
    "hi": ["deepgram", "scribe", "gemini", "hf"],   # Tier-3
    "ur": ["scribe", "gemini", "hf"],               # Tier-3: Deepgram ur support weaker
    # add "uk" extras (parakeet-uk/nemotron) here once the NIM function-id is wired
}


def _witness_call(name, audio_path, lang):
    from .witness import elevenlabs_read, deepgram_read, gemini_read, hf_read, whisper_local
    if name == "scribe":   return elevenlabs_read(audio_path, None)
    if name == "deepgram": return deepgram_read(audio_path, language=lang)
    if name == "gemini":   return gemini_read(audio_path, language=lang)
    if name == "hf":       return hf_read(audio_path, language=lang)
    if name == "whisper":  return whisper_local(audio_path, language=lang)
    return ""


# Witnesses with a single-call size/credit cap. On long audio these are auto-chopped
# into overlapping sections and stitched; the whole-file witnesses are called once.
CHOP_LIMITED = {"scribe", "hf"}
_CHOP_WINDOW_S = 110
_CHOP_OVERLAP_S = 20


def _splice(a, b, win=60, min_anchor=4):
    """Stitch chunk-read b onto a by removing the duplicated overlap at the seam.

    The two chunks share ~overlap_s of audio, but ASR transcribes those boundary words a
    little differently per chunk, so an EXACT suffix==prefix match fails. Instead we fuzzy-
    align A's tail against B's head (difflib) and cut both at the matched overlap block:
    keep A up to where the shared run starts, keep B from where it ends. Returns
    (merged, seam_ok); seam_ok=False => no convincing overlap found (a possible loss),
    surfaced rather than silently concatenated. This is the 're-listen to the seam' check."""
    aw, bw = a.split(), b.split()
    if not aw:
        return b, True
    if not bw:
        return a, True
    tail = aw[-win:]                                  # A's trailing words
    head = bw[:win]                                   # B's leading words
    sm = difflib.SequenceMatcher(None, [w.lower() for w in tail], [w.lower() for w in head])
    m = sm.find_longest_match(0, len(tail), 0, len(head))
    if m.size >= min_anchor:
        # cut A at the start of the shared run, B at the end of it -> overlap kept once
        keep_a = aw[:len(aw) - len(tail) + m.a]
        keep_b = bw[m.b + m.size:]
        return " ".join(keep_a + tail[m.a:m.a + m.size] + keep_b), True
    return " ".join(aw + bw), False                   # no anchor: concat + flag the seam


def _transcribe_chunks(chunks, name, lang, max_workers=3):
    """Run witness `name` over a list of (idx, off, path) chunks, in parallel, order-preserved."""
    import concurrent.futures
    parts = [""] * len(chunks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_witness_call, name, cp, lang): k for k, (_, _, cp) in enumerate(chunks)}
        for f in concurrent.futures.as_completed(futs):
            try:
                parts[futs[f]] = f.result() or ""
            except Exception:
                parts[futs[f]] = ""
    return parts


def _chopped_witness(name, audio_path, lang):
    """Chop long audio into OVERLAPPING sections, transcribe (parallel), stitch at the seams.
    Consecutive chunks share `_CHOP_OVERLAP_S` of audio at their EDGES — exactly where the
    splicer looks — so the overlap dedups cleanly and no word is dropped at a cut. The
    splicer's search window is sized to the overlap (fast speech ≈ 3 words/s) plus headroom.
    Returns (full_text, bad_seam_count)."""
    from . import chunking
    # Prefer silence-aware (VAD) cuts so no word is split at a seam; fall back to fixed windows.
    chunks = chunking.split_audio_vad(audio_path, window_s=_CHOP_WINDOW_S, overlap_s=_CHOP_OVERLAP_S) \
        or chunking.split_audio(audio_path, window_s=_CHOP_WINDOW_S, overlap_s=_CHOP_OVERLAP_S)
    if not chunks:
        return "", 0
    parts = _transcribe_chunks(chunks, name, lang)
    win = int(_CHOP_OVERLAP_S * 3.5) + 20            # words spanning the overlap region + slack
    full = parts[0]
    bad = 0
    for nxt in parts[1:]:
        if not nxt:
            bad += 1; continue
        full, ok = _splice(full, nxt, win=win)
        bad += (not ok)
    return full, bad


def _merge_diarized_chunks(chunk_turns, overlap_s):
    """Merge per-chunk diarized turns (already offset-rebased) into one timeline.

    Each chunk's diarizer emits its OWN speaker ids (scribe: speaker_0/1 per chunk), so ids
    are NOT comparable across chunks. We reconcile them at each seam: in the overlap window
    both chunks transcribe the same voices, so time-overlap voting maps the new chunk's ids
    onto the running global frame. Turns are then spliced at the overlap midpoint (prev chunk
    owns up to the midpoint, new chunk owns after) so the shared seconds aren't double-counted.
    chunk_turns: list of (offset, [{start,end,speaker,text}]) in order. Returns merged turns.
    """
    from . import speaker_consensus
    chunk_turns = [(off, t) for off, t in chunk_turns if t]
    if not chunk_turns:
        return []
    merged = [dict(t) for t in chunk_turns[0][1]]
    for off, turns in chunk_turns[1:]:
        seam, ov_end, mid = off, off + overlap_s, off + overlap_s / 2.0
        idmap = speaker_consensus.map_ids(merged, turns, seam, ov_end)  # new id -> global id
        relabeled = []
        for t in turns:
            t = dict(t)
            t["speaker"] = idmap.get(t["speaker"], f"spk_{off:.0f}_{t['speaker']}")
            relabeled.append(t)
        merged = [t for t in merged if t["start"] < mid] + [t for t in relabeled if t["start"] >= mid]
    merged.sort(key=lambda t: t["start"])
    return merged


def diarize_consensus(audio_path, lang, diarizers=("deepgram", "pyannote")):
    """Run several independent whole-file diarizers and cross-check them (Phase 0 capstone).

    Each diarizer is run via `diarize_long` (whole-file preferred, chunk fallback). GRACEFUL:
    a diarizer that errors or returns nothing (no credits / 4xx) is SKIPPED and recorded in
    `dropped` — never fatal, never a silent empty. The survivors go through cross-diarizer
    consensus: agreement = confidence, disagreement = flagged for review. First diarizer listed
    is the timing reference (default Deepgram — acoustic, reliable for speaker COUNT).

    Returns the cross_consensus dict plus `dropped` {name: reason}. With <2 survivors there's
    no consensus to take (returns the single diarization, agreement_pct=None)."""
    from . import chunking, speaker_consensus
    sources, dropped = {}, {}
    for n in diarizers:
        try:
            t = diarize_long(audio_path, lang, n)
            if t:
                sources[n] = t
            else:
                dropped[n] = "empty (no credits / no output)"
        except Exception as e:
            dropped[n] = repr(e)[:100]
    dur = chunking.probe(audio_path)[0] if chunking.have_ffmpeg() else 0.0
    if not dur:
        dur = max((x["end"] for ts in sources.values() for x in ts), default=0.0)
    rep = speaker_consensus.cross_consensus(sources, 0, dur)
    rep["dropped"] = dropped
    return rep


def diarize_long(audio_path, lang, diarizer="scribe"):
    """Production long-audio diarization (the reference-map architecture, measurement-backed).

    A whole-file diarizer pass gives globally-consistent speaker ids — correct for any file
    within the single-call limit (most real jobs), and the witnesses now retry on the transient
    large-upload errors that used to force chopping. So we PREFER whole-file; only if that fails
    (file genuinely too long for one call) do we fall back to chunk-only reconciliation (~90%
    agreement — voice embeddings are the future fix for that tail case).

    Measured on the Ubiqus 11-min file: whole-file/reference-map = 95.8% diar-agreement, 3 speakers;
    chunk-only = ~90%, over-counts speakers. Returns [{start, end, speaker, text}].
    """
    from . import witness
    fn = {"scribe": witness.elevenlabs_diarize,
          "deepgram": witness.deepgram_structured,
          "pyannote": witness.pyannote_diarize}.get(diarizer)
    if fn is None:
        raise ValueError(f"unknown diarizer {diarizer!r}")
    try:
        turns = fn(audio_path, lang)
        if turns:
            return turns                       # whole-file succeeded — globally-consistent ids
    except Exception:
        pass
    return chopped_diarize(audio_path, lang, diarizer)   # too long for one call → chunk fallback


def chopped_diarize(audio_path, lang, diarizer="scribe"):
    """Long-audio diarization for a capped diarizer (default ElevenLabs Scribe). Chops the
    file, diarizes each chunk (parallel), rebases timestamps, and reconciles speaker ids
    across seams. Returns unified [{start,end,speaker,text}]. The whole-file diarizer call
    SSL/size-fails past ~5 min; this is what makes the 2nd acoustic diarizer work on long audio."""
    import concurrent.futures
    from . import chunking, witness
    fn = {"scribe": witness.elevenlabs_diarize}.get(diarizer)
    if fn is None:
        raise ValueError(f"unknown diarizer {diarizer!r}")
    chunks = chunking.split_audio(audio_path, window_s=_CHOP_WINDOW_S, overlap_s=_CHOP_OVERLAP_S)
    results = [None] * len(chunks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(fn, cp, lang): k for k, (_, _, cp) in enumerate(chunks)}
        for f in concurrent.futures.as_completed(futs):
            try:
                results[futs[f]] = f.result() or []
            except Exception:
                results[futs[f]] = []
    chunk_turns = []
    for (idx, off, _), turns in zip(chunks, results):
        for t in (turns or []):
            t["start"] += off; t["end"] += off
        chunk_turns.append((off, turns or []))
    return _merge_diarized_chunks(chunk_turns, _CHOP_OVERLAP_S)


def roster_panel(audio_path, lang, seams=None):
    """Run this language's roster, concurrently. Whole-file witnesses are called once;
    size/credit-capped witnesses (scribe, hf) are auto-chopped+stitched on long audio so
    they participate instead of silently failing. `seams` (optional dict) is filled with
    {model: bad_seam_count} for the chopped witnesses. Returns {model: text}."""
    import concurrent.futures
    from . import chunking
    dur = chunking.probe(audio_path)[0] if chunking.have_ffmpeg() else 0.0
    long = dur > _CHOP_WINDOW_S

    def one(name):
        if long and name in CHOP_LIMITED:
            txt, bad = _chopped_witness(name, audio_path, lang)
            if seams is not None:
                seams[name] = bad
            return txt
        return _witness_call(name, audio_path, lang)

    reads = {}
    names = list(ROSTER.get(lang, []))
    if "whisper" not in names:                  # local Whisper: free, multilingual, always-on
        try:
            import faster_whisper  # noqa: F401
            names.append("whisper")
        except Exception:
            pass
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(names))) as ex:
        futs = {ex.submit(one, n): n for n in names}
        for f in concurrent.futures.as_completed(futs):
            try:
                reads[futs[f]] = f.result()
            except Exception:
                reads[futs[f]] = ""
    return {n: reads.get(n, "") for n in names}    # stable roster order


def _norm_ws(s):
    import re
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", s.lower().replace("ё", "е"))).strip()


def consensus_vote(reads):
    """Majority vote across the rostered reads; medoid (min total distance) breaks ties.
    Because the roster already excludes wrong-language witnesses, the majority is trustworthy."""
    cands = [t for t in reads.values() if t]
    if not cands:
        return ""
    from collections import Counter
    c = Counter(_norm_ws(t) for t in cands)
    top, n = c.most_common(1)[0]
    if n >= 2:
        for t in cands:
            if _norm_ws(t) == top:
                return t
    return min(cands, key=lambda a: sum(
        1 - difflib.SequenceMatcher(a=_norm_ws(a), b=_norm_ws(b)).ratio() for b in cands))


def _stretch(audio_path, rate):
    """Time-stretch audio to `rate`x speed, PITCH PRESERVED (ffmpeg atempo). rate<1 = slower.
    Returns a temp file path, or None if ffmpeg is unavailable / fails. Caller deletes it."""
    if rate >= 0.999:
        return None
    # atempo only accepts 0.5..2.0 per filter; chain if we ever go below 0.5
    chain = []
    r = rate
    while r < 0.5:
        chain.append("atempo=0.5")
        r /= 0.5
    chain.append(f"atempo={r:.4f}")
    fd, out = tempfile.mkstemp(suffix=".wav", prefix="ttslow_")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-filter:a", ",".join(chain), out],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        if os.path.exists(out):
            os.remove(out)
        return None


def _majority(reads):
    """How many witnesses agree on the single most-common normalized read (0 if none)."""
    from collections import Counter
    cands = [t for t in reads.values() if t]
    if not cands:
        return 0
    return Counter(_norm_ws(t) for t in cands).most_common(1)[0][1]


def transcribe(audio_path, lang, slow_rates=(0.65, 0.5)):
    """Top-level language-aware transcription: rostered panel -> consensus text.

    When the normal-speed panel does NOT reach a clear majority (the witnesses disagree —
    "we don't know"), automatically re-run the roster on PITCH-PRESERVED slowed audio and
    fold those reads into the vote. Slowing reliably makes uncertain witnesses converge on
    what's actually said (proved out on the Quicktate ES clips). Applies to ALL languages.
    A normal-speed majority short-circuits — no slow pass needed, no wasted API calls.
    Slowed reads are keyed `model@0.65x` so they stay visible and auditable.
    """
    reads = roster_panel(audio_path, lang)
    slowed_used = []
    # Only escalate when normal speed is ambiguous (< 2 witnesses agreeing).
    if _majority(reads) < 2:
        for rate in slow_rates:
            sp = _stretch(audio_path, rate)
            if not sp:
                continue
            try:
                for name, txt in roster_panel(sp, lang).items():
                    if txt:
                        reads[f"{name}@{rate:g}x"] = txt
                slowed_used.append(rate)
            finally:
                os.remove(sp)
            if _majority(reads) >= 2:   # converged — stop slowing
                break
    return {"text": consensus_vote(reads), "reads": reads, "lang": lang,
            "slowed": slowed_used, "agreement": _majority(reads)}


def _tok(text):
    # content tokens only — punctuation/space differ between models and aren't disagreements
    return [m.surface() for m in _toks(text)
            if m.part_of_speech()[0] not in ("補助記号", "空白", "記号")]


def panel(audio_path, language="ja"):
    """Run all available acoustic witnesses on the audio. Returns {model: text}."""
    reads = {}
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel("medium", device="cpu", compute_type="int8")
        segs, _ = m.transcribe(audio_path, language=language, task="transcribe")
        reads["whisper"] = "".join(s.text for s in segs).strip()
    except Exception as e:
        reads["whisper"] = ""
    from .witness import elevenlabs_read, deepgram_read, gemini_read
    try:
        reads["scribe"] = elevenlabs_read(audio_path)
    except Exception:
        reads["scribe"] = ""
    try:
        reads["deepgram"] = deepgram_read(audio_path, language=language)
    except Exception:
        reads["deepgram"] = ""
    try:
        reads["gemini"] = gemini_read(audio_path)
    except Exception:
        reads["gemini"] = ""
    return reads


def completeness(base, final):
    """Did the final transcript keep the Japanese content of the complete base read?
    Catches the dropped-content failure mode the auditor is blind to (it grades what's
    THERE, not what's MISSING). Returns the fraction of base Japanese content words that
    survived; < ~0.7 means content was dropped."""
    from .language import lang_of
    bt = [w for w in _tok(base) if lang_of(w) == "ja" and len(w) > 1]
    if not bt:
        return 1.0
    present = sum(1 for w in bt if w in final)
    return present / len(bt)


def consensus(reads):
    """Align the two STRONGEST non-empty reads (roster-agnostic — no hardcoded witnesses);
    any remaining models break ties. Returns the base (the medoid — the read closest to all
    others), the agreement %, and the disagreement spans to check. Whichever two witnesses
    survived (Deepgram+Gemini, Scribe+Whisper, …), the consensus is taken over them."""
    nonempty = {k: v for k, v in reads.items() if v}
    names = list(nonempty)
    if len(names) < 2:
        return {"base": nonempty[names[0]] if names else "", "agreement_pct": 0,
                "splits": [], "n_models": len(names), "base_model": names[0] if names else None}

    def dist(x, y):
        return 1 - difflib.SequenceMatcher(a=_norm_ws(x), b=_norm_ws(y)).ratio()
    # base = medoid (min total distance to the others) = the most-corroborated read
    base_name = min(names, key=lambda x: sum(dist(nonempty[x], nonempty[y]) for y in names if y != x))
    others = [n for n in names if n != base_name]
    other_name = min(others, key=lambda y: dist(nonempty[base_name], nonempty[y]))
    base, other = nonempty[base_name], nonempty[other_name]
    tiebreak = [nonempty[n] for n in names if n not in (base_name, other_name)]

    a, b = _tok(other), _tok(base)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    agreed = disagreed = 0
    splits = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            agreed += i2 - i1
            continue
        oseg, bseg = "".join(a[i1:i2]).strip(), "".join(b[j1:j2]).strip()
        if not oseg and not bseg:
            continue
        disagreed += max(i2 - i1, j2 - j1)
        backed = (base_name if (bseg and any(bseg in t for t in tiebreak))
                  else other_name if (oseg and any(oseg in t for t in tiebreak))
                  else "neither")
        splits.append({other_name: oseg or "—", base_name: bseg or "—", "backed_by_tiebreak": backed})
    pct = 100 * agreed // max(agreed + disagreed, 1)
    return {"base": base, "base_model": base_name, "other_model": other_name,
            "agreement_pct": pct, "splits": splits, "n_models": len(names)}
