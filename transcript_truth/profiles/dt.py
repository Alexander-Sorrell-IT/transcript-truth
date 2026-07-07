"""Daily Transcription profile — DT's own style guide, NOT GoTranscript.

Deliberately excludes en_format/_CV_FILLERS-style scanners: DT keeps 'yeah' and
'you know', mandates two-space label gaps and five-space timecode gaps (the generic
double-space check would false-flag them), and uses its own tag vocabulary
([indiscernible], not [inaudible HH:MM:SS])."""
from ._base import Profile, register
from ..dt_rules import DT_SCANNERS

register(Profile(
    name="dt",
    description="Daily Transcription style guide (verbatim, timecoded, DT tag vocabulary)",
    scanners=tuple(DT_SCANNERS),
    default_mode="verbatim",
    aliases=("daily", "dailytranscription"),
))
