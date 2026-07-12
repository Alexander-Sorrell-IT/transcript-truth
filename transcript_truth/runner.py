"""End-to-end transcription runner: audio + language -> draft (with timestamps +
speaker labels) -> QA -> formatted, submittable transcript. The missing wire between
the consensus/witness layer and the QA engine.

Flow: probe -> chunk if long -> Deepgram-structured per chunk (timestamps+speakers,
offset-rebased) -> format per mode -> audit the content with the language profile.
Deepgram is the structured backbone (0% WER on tests); the other witnesses remain
available as a text cross-check.
"""
from __future__ import annotations
import re
import difflib
from . import chunking, witness
from .engine import audit_transcript

# Deepgram space-separates CJK; Japanese uses no spaces. Strip spaces only when BOTH
# neighbours are non-ASCII, so English words inside a JP line keep their spacing.
_CJK_SPACE = re.compile(r"(?<=[^\x00-\x7f])\s+(?=[^\x00-\x7f])")


def _clean(text: str, lang: str) -> str:
    return _CJK_SPACE.sub("", text) if lang == "ja" else text

# SINGLE routing source of truth: language.PROFILE_FOR (bug-hunt 2026-07-11: a stale 5-entry
# duplicate here silently routed de/fr/pt/tr/vi/ko/ar/hi/ur to 'default' in the product path)
from .language import PROFILE_FOR as LANG_PROFILE
_CHUNK_OVER_S = 660  # chunk files longer than ~11 min


def _ts(s: float) -> str:
    return f"[{int(s // 60):02d}:{int(s % 60):02d}]"


def _utterances(audio_path: str, lang: str, _window_s: int = 600, _overlap_s: int = 5):
    dur, _ = chunking.probe(audio_path)
    if dur > _CHUNK_OVER_S and chunking.have_ffmpeg():
        out = []
        for idx, off, cp in chunking.split_audio(audio_path, window_s=_window_s,
                                                 overlap_s=_overlap_s):
            for u in witness.deepgram_structured(cp, lang):
                # seam ownership (bug-hunt 2026-07-11: blind concat double-transcribed every
                # overlap): each chunk owns [0, window); the tail past the window is the next
                # chunk's territory. A non-first chunk also drops utterances starting AT the cut
                # (<0.5s) — those are mid-utterance continuations the previous chunk already
                # emitted in full via its overlap tail.
                if u["start"] >= _window_s:
                    continue
                if idx > 0 and u["start"] < 0.5:
                    continue
                u["start"] += off; u["end"] += off
                out.append(u)
        return out
    return witness.deepgram_structured(audio_path, lang)


def _redistribute(utterances, corrected_text):
    """Merge consensus TEXT onto the Deepgram STRUCTURE (MODEL_MAP.md Stage H): keep each
    utterance's timestamps + speaker, but replace its WORDS with the aligned slice of the
    multi-model consensus text. Aligns the corrected tokens to the concatenated utterance tokens
    (difflib) and redistributes them to the utterance that owned each anchor position."""
    dg_tokens, owner = [], []
    for ui, u in enumerate(utterances):
        for w in u["text"].split():
            dg_tokens.append(w); owner.append(ui)
    ctoks = corrected_text.split()
    if not dg_tokens or not ctoks:
        return utterances
    sm = difflib.SequenceMatcher(a=[t.lower() for t in dg_tokens],
                                 b=[t.lower() for t in ctoks], autojunk=False)
    words = [[] for _ in utterances]
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "delete":
            continue                                  # consensus dropped these words
        if op == "equal":                             # 1:1 — assign each token to its own owner
            for k in range(i1, i2):
                words[owner[k]].append(ctoks[j1 + (k - i1)])
        else:                                         # replace/insert -> owner of the anchor start
            ui = owner[i1] if i1 < len(owner) else owner[-1]
            words[ui].extend(ctoks[j1:j2])
    return [{**u, "text": " ".join(words[ui]) or u["text"]} for ui, u in enumerate(utterances)]


def transcribe(audio_path: str, lang: str, profile: str | None = None,
               mode: str = "clean_verbatim", multi_model: bool = True, consensus_fn=None):
    """End-to-end: audio -> draft (timestamps+speakers) -> QA. Returns {transcript, content,
    receipt, lang, profile, n_utterances, multi_model}.

    multi_model (default ON) merges the MULTI-MODEL consensus text onto Deepgram's structure —
    Deepgram supplies the timestamps + speaker turns (its acoustic backbone), the consensus vote
    supplies the WORDS. So the end-to-end path is no longer single-model. Falls back to Deepgram's
    own text if the consensus is empty (no keys/offline). `consensus_fn` (no-arg -> text) injectable."""
    profile = profile or LANG_PROFILE.get(lang, "default")
    utts = _utterances(audio_path, lang)              # Deepgram structural backbone
    for u in utts:
        u["text"] = _clean(u["text"], lang)
    gate = None
    if multi_model and utts:
        if consensus_fn is None:
            from . import consensus
            _cres = {}
            def consensus_fn():
                _cres.update(consensus.transcribe(audio_path, lang) or {})
                return _cres.get("text", "")
        else:
            _cres = None
        ctext = _clean(consensus_fn() or "", lang)
        if ctext:
            utts = _redistribute(utts, ctext)         # consensus words, Deepgram timing/speakers
        if _cres is not None:
            gate = _cres.get("gate")
        if not ctext:
            # HARD GATE (Phase V): a multi-model job whose consensus came back empty is running
            # single-model — it may ship, but never as confident output
            gate = {"status": "review", "reasons": ["consensus empty — single-model fallback"],
                    "contested_ratio": None, "families": 1}
    formatted = "\n".join(f"{_ts(u['start'])} Speaker {u['speaker'] + 1}: {u['text']}" for u in utts)
    content = "\n".join(u["text"] for u in utts)
    receipt = audit_transcript(content, mode=mode, profile=profile)
    return {"transcript": formatted, "content": content, "receipt": receipt,
            "lang": lang, "profile": profile, "n_utterances": len(utts),
            "multi_model": bool(multi_model),
            "gate": gate or {"status": "review", "reasons": ["no consensus gate available"],
                             "contested_ratio": None, "families": None}}


# Term-accuracy rules where a mis-transcription is high-stakes (drug names, dosages, dangerous
# abbreviations, verified medical/legal terms) — these drive the re-examination loop.
_CRITICAL_DOMAIN_RULES = {"med_drug_name", "med_dosage", "med_dangerous_abbrev",
                          "med_umls_term", "legal_term"}


def _critical_domain_flags(receipt):
    return [f for f in receipt.flags
            if f.rule in _CRITICAL_DOMAIN_RULES or f.severity == "critical"]


def transcribe_domain_verified(audio_path: str, lang: str, domain: str,
                               mode: str = "clean_verbatim", max_rounds: int = 2,
                               transcribe_fn=None):
    """High-stakes legal/medical re-examination loop (MODEL_MAP.md Stage 4).

    Transcribe (normal+slow — `domain` forces the slow tier), audit against the domain guide, and
    if a CRITICAL term is still flagged, re-read + re-audit — up to `max_rounds` — because a mis-heard
    drug name or legal term is the costliest error. Stops early when the transcript is clean of
    critical flags OR a re-read changes nothing (stable). `transcribe_fn` (no-arg) is injectable; it
    defaults to the multi-model consensus transcription for this domain.
    Returns {content, receipt, rounds, resolved, remaining_flags, lang, profile, domain}."""
    profile = LANG_PROFILE.get(lang, "default")
    if transcribe_fn is None:
        from . import consensus
        transcribe_fn = lambda: consensus.transcribe(audio_path, lang, domain=domain)

    content, receipt, rounds = None, None, 0
    while rounds < max_rounds:
        rounds += 1
        new_content = (transcribe_fn() or {}).get("text", "")
        if content is not None and new_content == content:
            break                                    # re-read changed nothing → stable, stop
        content = new_content
        receipt = audit_transcript(content, mode=mode, profile=profile, domain=domain)
        if not _critical_domain_flags(receipt):
            break                                    # clean of critical terms → done
    return {"content": content, "receipt": receipt, "rounds": rounds,
            "resolved": not _critical_domain_flags(receipt),
            "remaining_flags": _critical_domain_flags(receipt),
            "lang": lang, "profile": profile, "domain": domain}


def transcribe_auto(audio_path: str, mode: str = "clean_verbatim"):
    """Auto-routed transcription: detect the language, then transcribe with that language's
    profile — no manual `lang`/`--profile` needed. Falls back to English if detection fails.
    Adds `detected` (the raw detected code) to the result."""
    from .language import detect, profile_for
    from .profiles import REGISTRY
    lang = detect(audio_path) or "en"
    prof = profile_for(lang)
    if prof not in REGISTRY:                  # language mapped but its profile isn't built yet
        prof = "default"                      # -> still run the mechanical checks, don't crash
    out = transcribe(audio_path, lang, prof, mode)
    out["detected"] = lang
    return out
