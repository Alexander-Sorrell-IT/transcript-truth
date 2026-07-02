"""Phase 4 — real audio I/O (chunking.py) exercised with a synthesized WAV via ffmpeg.

ffmpeg is present on this machine, so these are REAL renders (not stubs): probe, time_stretch,
cut_window, split_audio. The graceful-degradation branches (no ffmpeg) are tested by
monkeypatching have_ffmpeg -> False.
"""
import os, sys, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from transcript_truth import chunking

_HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
pytestmark = pytest.mark.skipif(not _HAVE_FFMPEG, reason="ffmpeg not installed")


@pytest.fixture
def wav(tmp_path):
    """~20s of 16kHz mono tone."""
    p = str(tmp_path / "tone.wav")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
                    "-ac", "1", "-ar", "16000", p, "-loglevel", "error"], check=True)
    return p


def test_have_ffmpeg_true():
    assert chunking.have_ffmpeg() is True


def test_probe_returns_duration_and_size(wav):
    dur, size = chunking.probe(wav)
    assert 19 < dur < 21 and size > 0


def test_time_stretch_slows_and_lengthens(wav):
    out = chunking.time_stretch(wav, 0.8)
    assert out and os.path.exists(out)
    orig_dur, _ = chunking.probe(wav)
    new_dur, _ = chunking.probe(out)
    assert new_dur > orig_dur                    # 0.8x speed => longer file


def test_time_stretch_extreme_rate_chains_atempo(wav):
    # rate 0.4 is below ffmpeg atempo's 0.5 floor -> must chain filters, not fail
    out = chunking.time_stretch(wav, 0.4)
    assert out and os.path.exists(out)


def test_time_stretch_invalid_rate_returns_none(wav):
    assert chunking.time_stretch(wav, 0) is None


def test_cut_window_extracts_segment(wav):
    out = chunking.cut_window(wav, start_s=5, length_s=6)
    assert out and os.path.exists(out)
    dur, _ = chunking.probe(out)
    assert 5 < dur < 7


def test_split_audio_produces_offset_chunks(wav):
    chunks = chunking.split_audio(wav, window_s=5, overlap_s=1, out_dir=str(wav) + "_c")
    assert len(chunks) >= 3                        # ~20s / 5s window
    idxs = [i for i, _, _ in chunks]
    offs = [off for _, off, _ in chunks]
    assert idxs == sorted(idxs)                    # ordered
    assert offs[0] == 0.0 and offs[1] == 5.0       # window_s spacing
    for _, _, cp in chunks:
        assert os.path.exists(cp)


def test_split_audio_without_ffmpeg_raises(monkeypatch, wav):
    monkeypatch.setattr(chunking, "have_ffmpeg", lambda: False)
    with pytest.raises(RuntimeError):
        chunking.split_audio(wav)


def test_time_stretch_without_ffmpeg_returns_none(monkeypatch, wav):
    monkeypatch.setattr(chunking, "have_ffmpeg", lambda: False)
    assert chunking.time_stretch(wav, 0.8) is None
