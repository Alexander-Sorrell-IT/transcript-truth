"""audio — the ASR front-end. Transcription is audio->text; this is where the tool
stops being a text checker and becomes a real transcription tool.

Strategy: run TWO Whisper engines (or two model sizes) and DIFF them — segments
where they disagree are the mishearing flags (the audio analogue of a homophone
trap). Kept optional (heavy deps) so the text pipeline runs without ASR installed:
    pip install faster-whisper
The full pipeline becomes:
    audio -> transcribe (xN) -> homophone_traps -> disambiguate -> receipt
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ASRResult:
    text: str
    segments: list = field(default_factory=list)   # [(start, end, text)]
    engine: str = ""


def transcribe(path: str, model: str = "small", lang: str = "ja") -> ASRResult:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError("pip install faster-whisper to use audio.transcribe") from e
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(path, language=lang)
    segments = [(s.start, s.end, s.text) for s in segs]
    return ASRResult(text="".join(s[2] for s in segments), segments=segments,
                     engine=f"faster-whisper/{model}")


def cross_check(path: str, models=("small", "medium"), lang: str = "ja") -> dict:
    """Two engines; disagreement = candidate mishearing to flag for review."""
    runs = [transcribe(path, m, lang) for m in models]
    a, b = runs[0].text.strip(), runs[1].text.strip()
    return {
        "texts": {r.engine: r.text for r in runs},
        "agree": a == b,
        "flag_mishearing": a != b,
        "primary": runs[0].text,
    }
