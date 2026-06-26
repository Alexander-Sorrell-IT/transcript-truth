"""CCSL conformance scanners — the QA half, pure stdlib regex/rule hits.

Mirrors `legal_rules.py`: each scanner is `(Transcript) -> list[Flag]`, every flag
is a deterministic regex hit cited at its line with a fix. No model, no network,
no third-party import — this module is auto-imported via `profiles/ccsl.py`, so it
MUST stay stdlib-only.

Severity discipline (the task contract):
  * `critical` ONLY for the three OBJECTIVE, mechanical timecode violations:
      - a timecode that is not a full four-part `HH:MM:SS:FF`;
      - `FF >= 30` (impossible at any standard rate — a loose mechanical bound,
        since the scanner can NOT see the real frame_rate);
      - `tc_out < tc_in` on an IN -> OUT row.
  * `moderate` for notation slips that are deterministically wrong (speaker/slug
    casing, lowercase sound prefixes).
  * `review` (weight 0, never moves the grade) for anything subjective (mode tag
    placement).

The scanner contract sees only `lines` — it does NOT thread `frame_rate` in (that
would break the `Scanner` signature and the profile wiring). It validates FORMAT,
not rate-relative range.
"""
from __future__ import annotations
import re
from .types import Flag, Transcript
from .ccsl_format import TC_RE, is_valid_tc, tc_to_frames


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# A timecode-ish token: 2..4 colon/semicolon-separated groups. Greedy, so a full
# `01:12:04:09` is grabbed whole and validated as conformant; `01:12:04` and `1:12`
# are grabbed as the shorter (wrong) shapes they are.
_TC_ISH = re.compile(r"\d{1,2}:\d{2}(?:[:;]\d{2}){0,2}")
# A leading "Name:"-style speaker label (no inner colon).
_SPEAKER = re.compile(r"^\s*([^:]{1,40}?):\s")
# A scene-heading slugline: line begins with INT/EXT.
_SLUG = re.compile(r"^\s*(int|ext)\b\.?", re.I)
# Whole-line slugline (for the fixer): begins with INT/EXT.
_SLUG_LINE = re.compile(r"^(\s*(?:int|ext)\b.*)$", re.I)
# A short parenthetical mode tag, e.g. (ON) (VO) (OS) (OFF).
_MODE = re.compile(r"\(([A-Za-z]{1,4})\)")
_VALID_MODES = {"ON", "VO", "OS", "OFF"}
# A leading sound prefix: MUSIC: / SFX:.
_SOUND_PREFIX = re.compile(r"^\s*(music|sfx)\s*:", re.I)

# sound prefixes are NOT speaker labels — skip them in the speaker-case scanner.
_NOT_SPEAKER = {"music", "sfx"}


# 1 -------------------------------------------------------------- timecode form
def ccsl_timecode(t: Transcript) -> list[Flag]:
    """The centerpiece: any timecode-ish token that is not a full four-part
    `HH:MM:SS:FF` is a hard violation. Fires on `01:12:04` (seconds-rounded) and
    `1:12` (wrong shape) — Gemini's `MM:SS` timing is never authoritative."""
    out: list[Flag] = []
    for ln in t.lines:
        for m in _TC_ISH.finditer(ln.text):
            tok = m.group(0)
            if not is_valid_tc(tok):
                out.append(_flag(
                    "ccsl_timecode", f"Timecode '{tok}' is not frame-accurate HH:MM:SS:FF",
                    ln.n, tok,
                    "Every CCSL timecode is a full four-part HH:MM:SS:FF (frame-accurate, "
                    "from ffprobe/ffmpeg) — never MM:SS or seconds-rounded.", "critical"))
    return out


# 2 ------------------------------------------------------------- frame in range
def ccsl_frame_range(t: Transcript) -> list[Flag]:
    """For any valid four-part token, FF >= 30 is impossible at any standard rate.
    Loose mechanical bound only — the scanner can NOT know the real frame rate."""
    out: list[Flag] = []
    for ln in t.lines:
        for m in TC_RE.finditer(ln.text):
            if int(m.group(5)) >= 30:
                out.append(_flag(
                    "ccsl_frame_range", f"Frame field '{m.group(0)}' has FF >= 30 (impossible)",
                    ln.n, m.group(0),
                    "FF must be < the frame rate; FF >= 30 is invalid at any standard rate.",
                    "critical"))
    return out


# 3 ------------------------------------------------------------- IN/OUT ordering
def ccsl_inout_order(t: Transcript) -> list[Flag]:
    """A row carrying two valid timecodes (IN then OUT) where OUT < IN is a hard
    error. Ties the formatter to the scanner: ordering is compared in integer
    frames at a fixed nominal N (monotonic in time, so rate-independent)."""
    out: list[Flag] = []
    for ln in t.lines:
        tcs = [m.group(0) for m in TC_RE.finditer(ln.text)]
        if len(tcs) < 2:
            continue
        try:
            f_in, f_out = tc_to_frames(tcs[0]), tc_to_frames(tcs[1])
        except ValueError:
            continue
        if f_out < f_in:
            out.append(_flag(
                "ccsl_inout_order", f"OUT '{tcs[1]}' precedes IN '{tcs[0]}'",
                ln.n, f"{tcs[0]} -> {tcs[1]}",
                "A shot/dialogue OUT timecode must not be earlier than its IN.",
                "critical"))
    return out


# 4 --------------------------------------------------------------- speaker case
def ccsl_speaker_case(t: Transcript) -> list[Flag]:
    """A speaker label that is not UPPERCASE — 'Maria:' should be 'MARIA:' (§6)."""
    out: list[Flag] = []
    for ln in t.lines:
        m = _SPEAKER.match(ln.text)
        if not m:
            continue
        label = m.group(1).strip()
        if label.lower() in _NOT_SPEAKER:
            continue
        if any(c.isalpha() for c in label) and label != label.upper():
            out.append(_flag(
                "ccsl_speaker_case", f"Speaker '{label}:' must be UPPERCASE",
                ln.n, f"{label}:",
                f"CCSL speaker labels are uppercase: '{label.upper()}:'."))
    return out


# 5 ---------------------------------------------------------------- scene heading
def ccsl_scene_heading(t: Transcript) -> list[Flag]:
    """A slugline (INT./EXT. …) that is not fully uppercased."""
    out: list[Flag] = []
    for ln in t.lines:
        if not _SLUG.match(ln.text):
            continue
        s = ln.text.strip()
        if s != s.upper():
            out.append(_flag(
                "ccsl_scene_heading", "Slugline must be UPPERCASE",
                ln.n, s,
                f"Scene headings are uppercase: '{s.upper()}'."))
    return out


# 6 ----------------------------------------------------------------- speaker mode
def ccsl_speaker_mode(t: Transcript) -> list[Flag]:
    """A parenthetical mode tag that isn't one of (ON)/(VO)/(OS)/(OFF). Placement
    is subjective -> surfaced as `review`, never moves the grade."""
    out: list[Flag] = []
    for ln in t.lines:
        for m in _MODE.finditer(ln.text):
            if m.group(1).upper() not in _VALID_MODES:
                out.append(_flag(
                    "ccsl_speaker_mode", f"Mode tag '{m.group(0)}' is not (ON)/(VO)/(OS)/(OFF)",
                    ln.n, m.group(0),
                    "CCSL voice-mode tags are (ON), (VO), (OS) or (OFF) — confirm this one.",
                    "review"))
    return out


# 7 ---------------------------------------------------------------- sound prefix
def ccsl_sound_prefix(t: Transcript) -> list[Flag]:
    """A lowercase MUSIC:/SFX: sound prefix — must be uppercase."""
    out: list[Flag] = []
    for ln in t.lines:
        m = _SOUND_PREFIX.match(ln.text)
        if m and m.group(1) != m.group(1).upper():
            out.append(_flag(
                "ccsl_sound_prefix", f"Sound prefix '{m.group(1)}:' must be UPPERCASE",
                ln.n, f"{m.group(1)}:",
                f"Sound cues use an uppercase prefix: '{m.group(1).upper()}:'."))
    return out


CCSL_SCANNERS = [
    ccsl_timecode, ccsl_frame_range, ccsl_inout_order,
    ccsl_speaker_case, ccsl_scene_heading, ccsl_speaker_mode, ccsl_sound_prefix,
]


# ===================================================================
# Fixers — deterministic auto-fix, (compiled_pattern, repl) pairs reusing the SAME
# compiled patterns the scanners detect with (detect and fix can never drift).
# ONLY ~always-correct casing fixes live here; timecode reshaping is deliberately
# OUT (the tool cannot invent frames).
CCSL_FIXERS = [
    (_SOUND_PREFIX, lambda m: m.group(1).upper() + ":"),   # music: -> MUSIC:
    (_SLUG_LINE, lambda m: m.group(1).upper()),            # int. house -> INT. HOUSE
]
