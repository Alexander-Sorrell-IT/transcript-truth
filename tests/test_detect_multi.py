"""Phase D — two-detector language id (MODEL_MAP.md Stage 0). Deepgram + local Whisper cross-check
so one detector can't misroute the whole job. Both detectors stubbed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import language, witness, chunking


def _stub(monkeypatch, dg, wh):
    monkeypatch.setattr(chunking, "have_ffmpeg", lambda: False)     # skip slicing
    monkeypatch.setattr(witness, "deepgram_detect_language", lambda p: dg)
    monkeypatch.setattr(witness, "whisper_detect_language", lambda p: wh)


def test_agree(monkeypatch):
    _stub(monkeypatch, "en", "en")
    r = language.detect_multi("x.wav")
    assert r["lang"] == "en" and r["agree"] is True and r["candidates"] == ["en"]


def test_disagree_lists_both_candidates(monkeypatch):
    _stub(monkeypatch, "ru", "uk")          # the classic ru/uk confusion
    r = language.detect_multi("x.wav")
    assert r["agree"] is False
    assert r["candidates"] == ["ru", "uk"]  # caller can try both rosters
    assert r["lang"] == "ru"                # Deepgram is primary


def test_whisper_fallback_when_deepgram_blank(monkeypatch):
    _stub(monkeypatch, "", "ja")
    assert language.detect_multi("x.wav")["lang"] == "ja"


def test_detect_returns_single_code(monkeypatch):
    _stub(monkeypatch, "es", "es")
    assert language.detect("x.wav") == "es"


def test_route_surfaces_disagreement(monkeypatch):
    _stub(monkeypatch, "ru", "uk")
    r = language.route("x.wav")
    assert r["lang"] == "ru" and r["detect_agree"] is False
    assert set(r["candidates"]) == {"ru", "uk"}
    assert isinstance(r["roster"], list)
