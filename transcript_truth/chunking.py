"""Long-audio chunking for the transcription pipeline. Gig audio is 30-60 min; ASR
APIs cap upload size/duration, so we split into time-windowed chunks (with overlap so
words aren't cut at seams) and the runner rebases each chunk's timestamps by its offset.
ffmpeg/ffprobe required (checked)."""
from __future__ import annotations
import os, json, subprocess, shutil


def have_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe(path: str):
    """(duration_seconds, size_bytes). duration 0.0 if ffprobe unavailable/fails."""
    dur = 0.0
    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "json", path],
                capture_output=True, text=True, timeout=30)
            dur = float(json.loads(out.stdout)["format"]["duration"])
        except Exception:
            dur = 0.0
    return dur, os.path.getsize(path)


def split_audio(path: str, window_s: int = 600, overlap_s: int = 5, out_dir: str | None = None):
    """Split into ~window_s chunks (+overlap). Returns [(idx, start_offset_s, chunk_path)].
    Each chunk is 16kHz mono WAV (ASR-friendly)."""
    if not have_ffmpeg():
        raise RuntimeError("ffmpeg/ffprobe required for long-audio chunking")
    dur, _ = probe(path)
    out_dir = out_dir or (path + "_chunks")
    os.makedirs(out_dir, exist_ok=True)
    chunks, i, start = [], 0, 0.0
    while start < (dur or 1):
        cp = os.path.join(out_dir, f"chunk_{i:03d}.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(start), "-t", str(window_s + overlap_s),
             "-i", path, "-ac", "1", "-ar", "16000", cp, "-loglevel", "error"],
            timeout=300)
        if os.path.getsize(cp) < 1000:
            os.remove(cp); break
        chunks.append((i, start, cp))
        i += 1; start += window_s
        if not dur:
            break
    return chunks
