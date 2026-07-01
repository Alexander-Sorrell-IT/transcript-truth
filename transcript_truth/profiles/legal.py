"""Legal profile — TranscribeMe Clean Verbatim for Legal (CVL), English.

Bundles the CVL-specific scanners (legal_rules.py) plus the shared, language-
neutral mechanical scanners (timestamps, spacing) that the CVL guide also wants.
Deliberately does NOT include the GoTranscript English scanners (en_format) or
the JP scanners — they encode rules that contradict CVL (see legal_rules.py).
"""
from ._base import Profile, register
from ..legal_rules import LEGAL_SCANNERS, LEGAL_FIXERS
from ..legal_terms import legal_terms
from ..tm_legal import tm_sound_tags, tm_lowercase_terms, tm_speaker_caps, tm_double_dash
from ..scanners import timestamps

register(Profile(
    name="legal",
    description="TranscribeMe Clean Verbatim for Legal (CVL), English",
    # + legal terminology + TranscribeMe training rules (sound tags, Bates lowercase, Colloquy caps, dashes)
    scanners=(timestamps, *LEGAL_SCANNERS, legal_terms,
              tm_sound_tags, tm_lowercase_terms, tm_speaker_caps, tm_double_dash),
    default_mode="clean_verbatim",
    aliases=("cvl", "transcribeme_legal"),
    fixers=tuple(LEGAL_FIXERS),              # Thoth: the legal "Redline" fixer set
))
