"""Default profile — the original engine: Japanese rules + GoTranscript English.

This reproduces the pre-profiles behavior exactly (ALL_SCANNERS), so existing
callers and tests are unchanged. Registered under "default" with aliases for the
two languages it actually covers.
"""
from ._base import Profile, register
from ..scanners import ALL_SCANNERS, DEFAULT_FIXERS

register(Profile(
    name="default",
    description="Japanese (GoTranscript) + GoTranscript English — the original engine",
    scanners=tuple(ALL_SCANNERS),
    aliases=("jp", "ja", "gotranscript"),
    fixers=tuple(DEFAULT_FIXERS),    # Thoth: language-safe mechanical removals
))
