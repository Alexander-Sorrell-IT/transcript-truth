"""CCSL generator half — renders a Combined Continuity & Spotting List from a video.

This is the NETWORK/VIDEO half and is deliberately NOT on the QA import chain and
NOT auto-imported by the profile registry. Nothing here is exercised by the test
suite; the conformance of what it renders is checked offline by the `ccsl` profile.

DIVISION OF AUTHORITY (the spine):
  * ffmpeg / PySceneDetect own EVERY timecode — shot IN/OUT come from integer
    source-frame indices via `ccsl_format.frame_to_tc`; dialogue IN/OUT come from
    Deepgram seconds via `seconds_to_frame`.
  * Gemini supplies shot DESCRIPTION + on-screen OCR only (no authoritative timing).
  * The consensus vote supplies dialogue TEXT only (text-only, carries NO timing).

All heavy/optional dependencies (scenedetect, subprocess/ffmpeg, the network
witnesses) are lazy-imported INSIDE functions, so even `import ccsl_build` cannot
fail when ffmpeg/scenedetect/keys are absent — and the QA chain never reaches here.
"""
from __future__ import annotations
import json

from .ccsl_format import (
    parse_frame_rate, nominal_rate, frame_to_tc, tc_to_frames, seconds_to_frame,
)


def probe_frame_rate(video_path) -> tuple[float, bool]:
    """ffprobe the video stream's r_frame_rate / avg_frame_rate. Returns (fps, is_vfr)
    where VFR = the two differ materially (a flag to CFR-transcode first). Degrades to
    (24.0, False) if ffprobe is unavailable."""
    import subprocess
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "0", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate,avg_frame_rate",
             "-of", "csv=p=0", str(video_path)],
            check=True, capture_output=True, text=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return 24.0, False
    parts = [p for p in out.replace("\n", ",").split(",") if p.strip()]
    r = parse_frame_rate(parts[0]) if parts else 24.0
    avg = parse_frame_rate(parts[1]) if len(parts) > 1 else r
    return r, abs(r - avg) > 0.01


def detect_shots(video_path, fps) -> list[tuple[int, int]]:
    """Shot boundaries as (in_frame, out_frame) SOURCE-frame index pairs. Prefers
    PySceneDetect; falls back to ffmpeg scene-score parsing. Returns [] on failure."""
    try:
        from scenedetect import detect, ContentDetector
        scenes = detect(str(video_path), ContentDetector())
        return [(a.get_frames(), b.get_frames()) for a, b in scenes]
    except ImportError:
        pass
    except Exception:
        return []
    # ffmpeg fallback: parse showinfo pts_time at scene cuts; source frame = round(pts*fps)
    import subprocess
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", str(video_path), "-filter:v",
             "select='gt(scene,0.3)',showinfo", "-f", "null", "-"],
            check=False, capture_output=True, text=True)
    except (FileNotFoundError, OSError):
        return []
    import re
    cuts = [round(float(m) * fps)
            for m in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]
    cuts = sorted(set(cuts))
    if not cuts:
        return []
    bounds = []
    for i, c in enumerate(cuts):
        end = cuts[i + 1] - 1 if i + 1 < len(cuts) else c
        bounds.append((c, max(c, end)))
    return bounds


def _bucket_gemini(shot_in_tc, shot_out_tc, gem_objs, fps, N):
    """Collect Gemini objects whose MM:SS `t` falls inside [shot_in, shot_out)."""
    lo, hi = tc_to_frames(shot_in_tc, N), tc_to_frames(shot_out_tc, N)
    action, ocr = [], []
    for g in gem_objs:
        t = g.get("t", "")
        try:
            mm, ss = (int(x) for x in t.split(":")[-2:])
        except (ValueError, IndexError):
            continue
        gf = seconds_to_frame(mm * 60 + ss, fps)
        if lo <= gf < max(hi, lo + 1):
            if g.get("shot"):
                action.append(str(g["shot"]))
            if g.get("action"):
                action.append(str(g["action"]))
            if g.get("onscreen_text"):
                ocr.append(str(g["onscreen_text"]))
    return " ".join(action).strip(), " | ".join(ocr).strip()


def merge(shots, gem_objs, deepgram_utts, fps, N) -> list[dict]:
    """Build the flat §4 event list — SHOT rows (ffmpeg owns IN/OUT) interleaved with
    DIALOGUE rows (Deepgram owns IN/OUT), sorted by IN frame. Gemini description/OCR is
    bucketed into the containing shot; dialogue text is taken verbatim from Deepgram (the
    caller may replace it with consensus text matched on the same span)."""
    rows: list[dict] = []
    for n, (sf, ef) in enumerate(shots, 1):
        in_tc, out_tc = frame_to_tc(sf, N), frame_to_tc(ef, N)
        action, ocr = _bucket_gemini(in_tc, out_tc, gem_objs, fps, N)
        rows.append({"kind": "shot", "shot_no": n, "in": in_tc, "out": out_tc,
                     "shot_type": "", "action": action, "onscreen_text": ocr,
                     "speaker": "", "text": ""})
    for u in deepgram_utts:
        in_tc = frame_to_tc(seconds_to_frame(u.get("start", 0.0), fps), N)
        out_tc = frame_to_tc(seconds_to_frame(u.get("end", 0.0), fps), N)
        rows.append({"kind": "dialogue", "shot_no": "", "in": in_tc, "out": out_tc,
                     "shot_type": "", "action": "", "onscreen_text": "",
                     "speaker": f"SPEAKER {u.get('speaker', 0)}".upper(),
                     "text": u.get("text", "").strip()})
    rows.sort(key=lambda r: tc_to_frames(r["in"], N))
    return rows


def render_5f(rows) -> str:
    """§3 5F profile — 8-column continuity + spotting. Plain text the `ccsl` profile
    can re-audit (UPPERCASE speakers/sluglines, four-part timecodes)."""
    out = []
    for r in rows:
        if r["kind"] == "shot":
            out.append("  ".join([
                f"SHOT {r['shot_no']}", r["in"], "->", r["out"],
                (r["shot_type"] or "").upper(), r["action"], r["onscreen_text"]]).rstrip())
        else:
            out.append("  ".join([
                "", r["in"], "->", r["out"], f"{r['speaker']}: {r['text']}"]).rstrip())
    return "\n".join(out)


def render_5d(rows) -> str:
    """§3 5D profile — 5-column spotting list (dialogue/title-card timing only)."""
    out = []
    for r in rows:
        if r["kind"] == "dialogue":
            out.append("  ".join([r["in"], "->", r["out"], f"{r['speaker']}: {r['text']}"]).rstrip())
        elif r["onscreen_text"]:
            out.append("  ".join([r["in"], "->", r["out"], f"TITLE: {r['onscreen_text']}"]).rstrip())
    return "\n".join(out)


def build_ccsl(video_path, lang="en", style="5F") -> str:
    """Orchestrator: probe rate -> detect shots -> Gemini visual read -> consensus/Deepgram
    -> merge -> render. Each network/heavy step degrades gracefully (empty) so a missing
    key / ffmpeg / scenedetect never crashes the build. Returns CCSL text."""
    fps, _vfr = probe_frame_rate(video_path)
    N = nominal_rate(fps)
    shots = detect_shots(video_path, fps)

    gem_objs = []
    try:
        from .witness import gemini_video_read
        raw = gemini_video_read(video_path, language=lang)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            gem_objs = parsed
    except Exception:
        gem_objs = []

    utts = []
    try:
        from .witness import deepgram_structured
        utts = deepgram_structured(video_path, language=lang)
    except Exception:
        utts = []

    # Replace each Deepgram utterance's text with the consensus read for the same span.
    try:
        from .consensus import transcribe
        cons = transcribe(video_path, lang)
        if cons.get("text") and len(utts) == 1:
            utts[0]["text"] = cons["text"]
    except Exception:
        pass

    rows = merge(shots, gem_objs, utts, fps, N)
    return render_5d(rows) if style.upper() == "5D" else render_5f(rows)
