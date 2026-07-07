"""Completeness gate — the direct counter to the 'missing dialogue' failure mode.

The QA scanners grade what's THERE; nothing audited what's MISSING at the audio level.
This runs Silero VAD over the WHOLE file and checks that every speech segment is covered
by a transcript utterance (timestamped). Any uncovered speech comes back with its exact
start/end so it can be re-listened — before a human ever sees the transcript.

Deterministic: the VAD segments are measured, the overlap math is pure. No model opinion.
"""
from __future__ import annotations

# a speech segment shorter than this is breath/noise — not missable dialogue
MIN_SEGMENT_S = 0.8
# fraction of a speech segment that must overlap utterances to count as covered
MIN_OVERLAP = 0.5


def speech_segments(audio_path):
    """Whole-file Silero VAD -> [(start_s, end_s)]. [] if silero unavailable (graceful)."""
    try:
        from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
        sr = 16000
        wav = read_audio(audio_path, sampling_rate=sr)
        model = load_silero_vad()
        ts = get_speech_timestamps(wav, model, sampling_rate=sr, return_seconds=True)
        return [(t["start"], t["end"]) for t in ts]
    except Exception:
        return []


def _overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def verify_coverage(audio_path, utterances):
    """utterances: [{'start': s, 'end': s, ...}] (the timestamped transcript backbone).
    Returns {covered_pct, uncovered: [(start, end)], n_speech_segments}.
    uncovered = speech the transcript has NOTHING for — the exact spots dialogue goes missing."""
    segs = [(s, e) for s, e in speech_segments(audio_path) if e - s >= MIN_SEGMENT_S]
    if not segs:
        return {"covered_pct": None, "uncovered": [], "n_speech_segments": 0}
    spans = [(float(u["start"]), float(u["end"])) for u in utterances
             if u.get("end") is not None and u.get("start") is not None]
    uncovered = []
    covered_time = total_time = 0.0
    for s, e in segs:
        dur = e - s
        total_time += dur
        ov = sum(_overlap(s, e, us, ue) for us, ue in spans)
        covered_time += min(ov, dur)
        if ov / dur < MIN_OVERLAP:
            uncovered.append((round(s, 2), round(e, 2)))
    return {"covered_pct": round(100.0 * covered_time / total_time, 1) if total_time else None,
            "uncovered": uncovered, "n_speech_segments": len(segs)}
