"""Phase 4 — check_audio.main orchestration + receipt, with the heavy ASR (asr) STUBBED.
The wav2vec2/whisper inference itself is model I/O (pragma no cover); this tests the wiring.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from transcript_truth import check_audio


def test_main_clean_when_transcript_matches_audio(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(check_audio, "asr", lambda *a, **k: "群島や湖では")
    audio = tmp_path / "clip.wav"; audio.write_bytes(b"x")
    rc = check_audio.main([str(audio), "--text", "群島や湖では"])
    out = capsys.readouterr().out
    assert rc == 0 and "clean" in out.lower()


def test_main_flags_mismatch(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(check_audio, "asr", lambda *a, **k: "群島や湖では")
    audio = tmp_path / "clip.wav"; audio.write_bytes(b"x")
    rc = check_audio.main([str(audio), "--text", "全く違う内容です"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "AUDIO SAYS" in out and "TRANSCRIPT" in out


def test_main_reads_transcript_file(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(check_audio, "asr", lambda *a, **k: "hello world")
    audio = tmp_path / "clip.wav"; audio.write_bytes(b"x")
    tr = tmp_path / "draft.txt"; tr.write_text("hello world")
    rc = check_audio.main([str(audio), "--transcript", str(tr)])
    assert rc == 0 and "clean" in capsys.readouterr().out.lower()


def test_main_missing_audio_errors(tmp_path):
    with pytest.raises(SystemExit):        # argparse p.error -> SystemExit(2)
        check_audio.main([str(tmp_path / "nope.wav"), "--text", "x"])
