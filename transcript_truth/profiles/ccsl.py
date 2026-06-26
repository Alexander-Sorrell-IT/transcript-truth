"""CCSL profile — Combined Continuity & Spotting List, frame-accurate conformance.

The QA half of the CCSL module: re-audits CCSL text rendered by `ccsl_build.py`
against the hard contract (four-part `HH:MM:SS:FF` timecodes, UPPERCASE speakers,
uppercase sluglines, bracketed/uppercase sound cues). Same pattern as legal/es —
the scanner checks *rendered conformance*; it is NOT the generator.

Imports only stdlib + the two pure CCSL modules, so package auto-discovery can
never turn the suite red (no scenedetect / ffmpeg / network on this chain).
"""
from ._base import Profile, register
from ..ccsl_rules import CCSL_SCANNERS, CCSL_FIXERS
from ..scanners import timestamps

register(Profile(
    name="ccsl",
    description="Combined Continuity & Spotting List (CCSL) — frame-accurate conformance, English",
    scanners=(timestamps, *CCSL_SCANNERS),
    default_mode="clean_verbatim",
    aliases=(),          # do NOT use "cvl" (legal owns it)
    fixers=tuple(CCSL_FIXERS),
))
