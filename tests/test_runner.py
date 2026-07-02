"""Phase 4 — runner.py end-to-end wire (audio -> draft -> QA), with the ASR witness STUBBED.
Also the pure helpers (_clean CJK-space handling, _ts timestamp formatting).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import runner


# ---------- pure helpers ----------

def test_ts_formats_mm_ss():
    assert runner._ts(0) == "[00:00]"
    assert runner._ts(75) == "[01:15]"


def test_clean_strips_space_between_cjk_only():
    # spaces between two Japanese chars are removed; spacing around English is kept
    assert runner._clean("これ は test です", "ja") == "これは test です"


def test_clean_noop_for_non_japanese():
    assert runner._clean("hello world", "en") == "hello world"


# ---------- transcribe(): full wire with stubbed Deepgram ----------

def test_transcribe_wires_asr_to_audit(monkeypatch, tmp_path):
    fake = str(tmp_path / "audio.wav")     # not real audio; probe -> dur 0 -> non-chunk path
    open(fake, "wb").write(b"not-audio")
    monkeypatch.setattr(runner.witness, "deepgram_structured",
                        lambda path, lang: [
                            {"start": 0.0, "end": 2.0, "speaker": 0, "text": "This is a clean line."},
                            {"start": 2.0, "end": 4.0, "speaker": 1, "text": "And so is this one."},
                        ])
    res = runner.transcribe(fake, "en", multi_model=False)
    assert res["n_utterances"] == 2
    assert "[00:00] Speaker 1: This is a clean line." in res["transcript"]
    assert res["receipt"].grade == "A"           # clean content -> grade A from the real auditor
    assert res["lang"] == "en" and res["profile"] == "en"


def test_transcribe_empty_audio_yields_no_utterances(monkeypatch, tmp_path):
    fake = str(tmp_path / "audio.wav")
    open(fake, "wb").write(b"x")
    monkeypatch.setattr(runner.witness, "deepgram_structured", lambda path, lang: [])
    res = runner.transcribe(fake, "en", multi_model=False)
    assert res["n_utterances"] == 0 and res["content"] == ""
