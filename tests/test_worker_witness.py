"""Phase 4 — worker.py (model-facing correction/witness) and witness.py helpers.

Model calls (qwen, ASR APIs) are STUBBED or left as genuine external I/O (pragma no cover).
Tested here: deterministic timestamp math, the homophone parse-gate, env-key lookup, and
real 16kHz WAV loading (ffmpeg present).
"""
import os, sys, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from transcript_truth import worker, witness


# ---------- worker.file_timestamp: pure math ----------

def test_file_timestamp_computed():
    # 60-min file in 4 parts => 15 min/part; part 2, +30s => 00:15:30
    assert worker.file_timestamp(60, 4, 2, 30) == "[00:15:30]"


def test_file_timestamp_embedded_overrides_math():
    assert worker.file_timestamp(60, 4, 2, 30, embedded_hms="1:02:03") == "[01:02:03]"


def test_file_timestamp_embedded_pads_short_form():
    assert worker.file_timestamp(0, 1, 1, 0, embedded_hms="5:07") == "[00:05:07]"


# ---------- worker.find_homophone_errors: parse gate (qwen stubbed) ----------

def test_find_homophone_errors_parses_pairs(monkeypatch):
    monkeypatch.setattr(worker, "qwen", lambda *a, **k: "菓子→華氏\n動機→動悸")
    pairs = worker.find_homophone_errors("菓子90度")
    assert ("菓子", "華氏") in pairs and ("動機", "動悸") in pairs


def test_find_homophone_errors_none_reply(monkeypatch):
    monkeypatch.setattr(worker, "qwen", lambda *a, **k: "なし")
    assert worker.find_homophone_errors("正しい文") == []


def test_correct_transcript_delegates_to_model(monkeypatch):
    monkeypatch.setattr(worker, "qwen", lambda msgs, **k: "corrected output")
    assert worker.correct_transcript("raw") == "corrected output"


# ---------- witness helpers ----------

def test_witness_key_from_env(monkeypatch):
    monkeypatch.setenv("SOME_TEST_KEY", "abc123")
    assert witness._key("SOME_TEST_KEY") == "abc123"


def test_witness_key_missing_raises(monkeypatch):
    monkeypatch.delenv("DEFINITELY_MISSING_KEY", raising=False)
    # falls through to .env scan; the key isn't there either -> RuntimeError
    with pytest.raises(RuntimeError):
        witness._key("DEFINITELY_MISSING_KEY")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_load_wav16_returns_mono_16k(tmp_path):
    p = str(tmp_path / "t.wav")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-ac", "1", "-ar", "16000", p, "-loglevel", "error"], check=True)
    wav = witness._load_wav16(p)
    assert getattr(wav, "ndim", 1) == 1 and len(wav) > 0
