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
from . import chunking, witness
from .engine import audit_transcript

# Deepgram space-separates CJK; Japanese uses no spaces. Strip spaces only when BOTH
# neighbours are non-ASCII, so English words inside a JP line keep their spacing.
_CJK_SPACE = re.compile(r"(?<=[^\x00-\x7f])\s+(?=[^\x00-\x7f])")


def _clean(text: str, lang: str) -> str:
    return _CJK_SPACE.sub("", text) if lang == "ja" else text

LANG_PROFILE = {"ja": "default", "ru": "ru", "uk": "uk", "es": "es", "en": "en"}
_CHUNK_OVER_S = 660  # chunk files longer than ~11 min


def _ts(s: float) -> str:
    return f"[{int(s // 60):02d}:{int(s % 60):02d}]"


def _utterances(audio_path: str, lang: str):
    dur, _ = chunking.probe(audio_path)
    if dur > _CHUNK_OVER_S and chunking.have_ffmpeg():
        out = []
        for _, off, cp in chunking.split_audio(audio_path):
            for u in witness.deepgram_structured(cp, lang):
                u["start"] += off; u["end"] += off
                out.append(u)
        return out
    return witness.deepgram_structured(audio_path, lang)


def transcribe(audio_path: str, lang: str, profile: str | None = None,
               mode: str = "clean_verbatim"):
    """Returns {transcript (formatted), content, receipt, lang, profile, n_utterances}."""
    profile = profile or LANG_PROFILE.get(lang, "default")
    utts = _utterances(audio_path, lang)
    for u in utts:
        u["text"] = _clean(u["text"], lang)
    formatted = "\n".join(f"{_ts(u['start'])} Speaker {u['speaker'] + 1}: {u['text']}" for u in utts)
    content = "\n".join(u["text"] for u in utts)
    receipt = audit_transcript(content, mode=mode, profile=profile)
    return {"transcript": formatted, "content": content, "receipt": receipt,
            "lang": lang, "profile": profile, "n_utterances": len(utts)}


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
