"""CCSL timecode formatter — frame-accurate SMPTE arithmetic, pure stdlib.

The spine decision for a Combined Continuity & Spotting List: every timecode is a
four-part `HH:MM:SS:FF` token and ALL arithmetic is done in INTEGER FRAMES — never
on the strings. A model's `MM:SS` guess is never authoritative; frames come from
ffprobe/ffmpeg and round-trip exactly through here.

No third-party imports anywhere on this module (it sits at the bottom of the
QA chain `profiles/ccsl.py -> ccsl_rules.py -> ccsl_format.py`, which the profile
registry auto-imports — so it must stay stdlib-only or it would redden the suite).

Drop-frame (29.97, `;FF` separator) is supported minimally: it parses and
round-trips via the standard SMPTE counting algorithm, but the non-drop colon
form is primary and is the only thing the scanners enforce as a hard contract.
"""
from __future__ import annotations
import re

# A full four-part SMPTE token. Group 4 (`:` vs `;`) distinguishes non-drop vs drop-frame.
TC_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})([:;])(\d{2})")


def is_valid_tc(s: str) -> bool:
    """True only for a full `HH:MM:SS:FF` / `HH:MM:SS;FF` token. Rejects `MM:SS`,
    `H:MM:SS` and any non-four-part shape (the scanner relies on this to reject
    seconds-rounded timing)."""
    return TC_RE.fullmatch(s.strip()) is not None


def parse_frame_rate(r: str) -> float:
    """`"24000/1001" -> 23.976`, `"24" -> 24.0`. Splits a rational on `/`."""
    r = r.strip()
    if "/" in r:
        num, den = r.split("/", 1)
        den = float(den) or 1.0
        return round(float(num) / den, 3)
    return float(r)


def nominal_rate(fps: float) -> int:
    """`round(fps)` snapped to a standard nominal rate {24,25,30} — used as `N` for
    TC formatting (23.976 -> 24, 29.97 -> 30, 25 -> 25)."""
    r = round(fps)
    std = (24, 25, 30)
    return r if r in std else min(std, key=lambda x: abs(x - r))


# ----------------------------------------------------------------- drop-frame
# Standard 29.97 drop-frame counting algorithm (Duncan/Heidelberger). Kept here
# only so the `;FF` form round-trips; non-drop is the primary path.
_DF_PER_10MIN = 17982          # frames in 10 drop-frame minutes
_DF_PER_MIN = 30 * 60 - 2      # frames in a dropped minute (drops 2)


def _frame_to_tc_drop(frame: int) -> str:
    frame %= 30 * 60 * 60 * 24
    d = frame // _DF_PER_10MIN
    m = frame % _DF_PER_10MIN
    if m > 2:
        frame += 2 * 9 * d + 2 * ((m - 2) // _DF_PER_MIN)
    else:
        frame += 2 * 9 * d
    ff = frame % 30
    s = frame // 30
    return f"{s//3600:02d}:{(s//60)%60:02d}:{s%60:02d};{ff:02d}"


def _tc_to_frames_drop(hh: int, mm: int, ss: int, ff: int) -> int:
    total_min = 60 * hh + mm
    return (108000 * hh) + (1800 * mm) + (30 * ss) + ff - 2 * (total_min - total_min // 10)


# ------------------------------------------------------------------ non-drop
def frame_to_tc(frame: int, N: int = 24, drop: bool = False) -> str:
    """Integer frame count -> `HH:MM:SS:FF`. Non-drop is `ff = frame % N`,
    `s = frame // N`. `drop=True` emits the 29.97 `;FF` form."""
    if drop:
        return _frame_to_tc_drop(frame)
    ff = frame % N
    s = frame // N
    return f"{s//3600:02d}:{(s//60)%60:02d}:{s%60:02d}:{ff:02d}"


def tc_to_frames(tc: str, N: int = 24) -> int:
    """`HH:MM:SS:FF` -> integer frame count. Drop-frame (`;`) uses the SMPTE
    inverse; non-drop uses `((hh*60+mm)*60+ss)*N + ff`. Raises ValueError on any
    non-four-part string (callers must pass real, validated timecodes)."""
    m = TC_RE.fullmatch(tc.strip())
    if not m:
        raise ValueError(f"not a four-part timecode: {tc!r}")
    hh, mm, ss, sep, ff = int(m[1]), int(m[2]), int(m[3]), m[4], int(m[5])
    if sep == ";":
        return _tc_to_frames_drop(hh, mm, ss, ff)
    return ((hh * 60 + mm) * 60 + ss) * N + ff


def seconds_to_frame(sec: float, fps: float) -> int:
    """The ONLY float -> frame path (reserved for dialogue start/end from Deepgram)."""
    return round(sec * fps)


def duration_tc(tc_in: str, tc_out: str, N: int = 24) -> str:
    """Duration between two timecodes, expressed as a TC (out - in, in frames)."""
    return frame_to_tc(tc_to_frames(tc_out, N) - tc_to_frames(tc_in, N), N)
