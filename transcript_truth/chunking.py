"""Long-audio chunking for the transcription pipeline. Gig audio is 30-60 min; ASR
APIs cap upload size/duration, so we split into time-windowed chunks (with overlap so
words aren't cut at seams) and the runner rebases each chunk's timestamps by its offset.
ffmpeg/ffprobe required (checked)."""
from __future__ import annotations
import os, json, subprocess, shutil


def have_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def time_stretch(path: str, rate: float = 0.8, out_path: str | None = None) -> str | None:
    """Slow-down-and-listen (CV guide p.2): re-render audio at a different SPEED without changing
    pitch, so ASR gets a second, clearer pass at fast/unclear speech. rate<1.0 = slower (0.8 = 80%
    speed), rate>1.0 = faster. Language- and mode-agnostic — operates on raw audio. ffmpeg's atempo
    filter is valid for 0.5–2.0; chain filters for values beyond that. Returns the new path (16kHz
    mono WAV) or None if ffmpeg is unavailable / the render fails."""
    if not have_ffmpeg() or rate <= 0:
        return None
    # decompose rate into a chain of atempo factors each within [0.5, 2.0]
    factors, r = [], rate
    while r < 0.5:
        factors.append(0.5); r /= 0.5
    while r > 2.0:
        factors.append(2.0); r /= 2.0
    factors.append(r)
    chain = ",".join(f"atempo={f:.4f}" for f in factors)
    out_path = out_path or (path + f".x{rate:.2f}.wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-filter:a", chain, "-ac", "1", "-ar", "16000",
             out_path, "-loglevel", "error"], timeout=300, check=True)
        return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 1000 else None
    except Exception:
        return None


def cut_window(path: str, start_s: float, length_s: float, out_path: str | None = None) -> str | None:
    """Extract a single [start, start+length] audio window (16kHz mono WAV). Used to cut a BRIDGE
    chunk straddling a specific seam on demand. Returns the path or None on failure."""
    if not have_ffmpeg():
        return None
    out_path = out_path or (path + f".w{start_s:.0f}_{length_s:.0f}.wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(max(0.0, start_s)), "-t", str(length_s), "-i", path,
             "-ac", "1", "-ar", "16000", out_path, "-loglevel", "error"], timeout=300, check=True)
        return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 1000 else None
    except Exception:
        return None


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
        if not os.path.exists(cp) or os.path.getsize(cp) < 1000:  # ffmpeg may have produced nothing
            if os.path.exists(cp):
                os.remove(cp)
            break
        chunks.append((i, start, cp))
        i += 1; start += window_s
        if not dur:
            break
    return chunks


def split_audio_vad(path: str, window_s: int = 110, overlap_s: int = 8, out_dir: str | None = None):
    """Silence-aware chunking via Silero VAD: cut at speech pauses near each ~window_s boundary
    instead of mid-word — fixing seam loss AT THE SOURCE. A small overlap is still added so the
    text splicer can align. Returns [(idx, start_s, path)] or None if silero/ffmpeg unavailable."""
    if not have_ffmpeg():
        return None
    try:
        from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
    except Exception:
        return None
    sr = 16000
    try:
        model = load_silero_vad()
        wav = read_audio(path, sampling_rate=sr)
        speech = get_speech_timestamps(wav, model, sampling_rate=sr, return_seconds=True)
    except Exception:
        return None
    dur = len(wav) / sr
    if not speech:
        return None
    # candidate cut points = midpoints of silence gaps between speech segments
    cuts = [0.0]
    for i in range(len(speech) - 1):
        gap_mid = (speech[i]["end"] + speech[i + 1]["start"]) / 2
        if gap_mid - cuts[-1] >= window_s * 0.7:   # chunk reached ~window -> cut at this silence
            cuts.append(gap_mid)
    cuts.append(dur)
    out_dir = out_dir or (path + "_vadchunks")
    os.makedirs(out_dir, exist_ok=True)
    chunks = []
    for i in range(len(cuts) - 1):
        start = max(0.0, cuts[i] - (overlap_s / 2 if i > 0 else 0.0))
        end = min(dur, cuts[i + 1] + overlap_s / 2)
        cp = os.path.join(out_dir, f"vad_{i:03d}.wav")
        subprocess.run(["ffmpeg", "-y", "-ss", str(start), "-t", str(end - start),
                        "-i", path, "-ac", "1", "-ar", "16000", cp, "-loglevel", "error"], timeout=300)
        if os.path.exists(cp) and os.path.getsize(cp) > 1000:
            chunks.append((i, start, cp))
    return chunks or None


def split_interleaved(path: str, window_s: int = 110, out_dir: str | None = None):
    """Phase-shifted chunking (the 'sections between the sections' design).

    Two passes so no word is ever clipped at a seam:
      primary  = [0,W], [W,2W], [2W,3W], ...        (a, b, c, d, e)
      boundary = [W/2,3W/2], [3W/2,5W/2], ...       (straddles each a|b, b|c seam)
    Every primary boundary (t=W, 2W, ...) sits in the MIDDLE of a boundary chunk, so the
    boundary chunk gives a clean, un-clipped read of that seam to bridge/verify against.
    Returns {"primary": [(i,off,path)], "boundary": [(i,off,path)]}.  16kHz mono WAV.
    """
    if not have_ffmpeg():
        raise RuntimeError("ffmpeg/ffprobe required for long-audio chunking")
    dur = probe(path)[0] or 1
    out_dir = out_dir or (path + "_ichunks")
    os.makedirs(out_dir, exist_ok=True)

    def cut(tag, idx, start, length):
        cp = os.path.join(out_dir, f"{tag}_{idx:03d}.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(max(0.0, start)), "-t", str(length),
             "-i", path, "-ac", "1", "-ar", "16000", cp, "-loglevel", "error"], timeout=300)
        return cp if os.path.exists(cp) and os.path.getsize(cp) > 1000 else None

    primary, boundary = [], []
    i, start = 0, 0.0
    while start < dur:
        cp = cut("p", i, start, window_s)
        if not cp:
            break
        primary.append((i, start, cp)); i += 1; start += window_s
    j, bstart = 0, window_s / 2.0
    while bstart < dur:
        cp = cut("b", j, bstart, window_s)
        if cp:
            boundary.append((j, bstart, cp))
        j += 1; bstart += window_s
    return {"primary": primary, "boundary": boundary}
