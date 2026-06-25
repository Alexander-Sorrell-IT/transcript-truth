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
    "ru": ["deepgram", "scribe", "hf", "gemini"],   # all usable; Deepgram strongest
    "uk": ["deepgram", "scribe"],                     # only these stay in Ukrainian; others drift
    "es": ["deepgram", "scribe", "hf", "gemini"],   # well-supported by all witnesses
    "en": ["deepgram", "scribe", "hf", "gemini"],
    # add "uk" extras (parakeet-uk/nemotron) here once the NIM function-id is wired
}


def _witness_call(name, audio_path, lang):
    from .witness import elevenlabs_read, deepgram_read, gemini_read, hf_read
    if name == "scribe":   return elevenlabs_read(audio_path, None)
    if name == "deepgram": return deepgram_read(audio_path, language=lang)
    if name == "gemini":   return gemini_read(audio_path, language=lang)
    if name == "hf":       return hf_read(audio_path, language=lang)
    return ""


def roster_panel(audio_path, lang):
    """Run only the witnesses on this language's roster. Returns {model: text}."""
    reads = {}
    for name in ROSTER.get(lang, []):
        try:
            reads[name] = _witness_call(name, audio_path, lang)
        except Exception:
            reads[name] = ""
    return reads


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
    """Align the two strong reads (Scribe, Whisper); Deepgram breaks ties. Returns the
    base (Scribe, the strongest), the agreement %, and the disagreement spans to check."""
    base = reads.get("scribe") or reads.get("whisper", "")
    other = reads.get("whisper", "")
    deep = reads.get("deepgram", "")
    a, b = _tok(other), _tok(base)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    agreed = disagreed = 0
    splits = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            agreed += i2 - i1
            continue
        wseg, sseg = "".join(a[i1:i2]).strip(), "".join(b[j1:j2]).strip()
        if not wseg and not sseg:
            continue
        disagreed += max(i2 - i1, j2 - j1)
        # Deepgram tiebreak: which version does the 3rd model corroborate?
        backed = "scribe" if (sseg and sseg in deep) else "whisper" if (wseg and wseg in deep) else "neither"
        splits.append({"whisper": wseg or "—", "scribe": sseg or "—", "deepgram_backs": backed})
    pct = 100 * agreed // max(agreed + disagreed, 1)
    return {"base": base, "agreement_pct": pct, "splits": splits,
            "n_models": sum(1 for v in reads.values() if v)}
