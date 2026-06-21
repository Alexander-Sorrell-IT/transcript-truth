"""Personal profile — Alex's CVL legal profile + his own recurring slips.

Layers personal_rules.py (the mistakes Alex actually makes in his drafts) on top
of the full legal (CVL) scanner set. Same deterministic spine, same study-aid
boundary as `legal`: this checks YOUR OWN practice/draft text for the mechanics
you tend to miss — it is not an exam autopilot and adds no model to the verdict.
"""
from ._base import Profile, register
from ..legal_rules import LEGAL_SCANNERS, LEGAL_FIXERS
from ..personal_rules import PERSONAL_SCANNERS, PERSONAL_FIXERS
from ..scanners import timestamps

register(Profile(
    name="me",
    description="Alex's personal profile — legal CVL + his recurring mechanical slips",
    scanners=(timestamps, *LEGAL_SCANNERS, *PERSONAL_SCANNERS),
    default_mode="clean_verbatim",
    aliases=("alex", "personal"),
    fixers=(*LEGAL_FIXERS, *PERSONAL_FIXERS),  # Thoth: legal Redline + Alex's apostrophe fixes
))
