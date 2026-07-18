"""GoTranscript × Japanese SITE layer — Japanese OUTPUT FORMAT for GoTranscript jobs.

Auto-discovered by `domains.autodiscover_domain_layers` via the `{site}_{lang}_rules.py` naming
convention (site='gotranscript', lang='ja'), exporting `JA_GOTRANSCRIPT_SCANNERS`. Its presence flips
the gotranscript × ja coverage slot from `core` (universal format only) to `full`.

The Japanese LANGUAGE rules (kana usage = GoTranscript rule 24) live in the `ja` profile and compose
in automatically, so `compose("ja", None, "gotranscript")` = kana usage + Japanese punctuation +
the universal core (timestamps, [inaudible HH:MM:SS], number style).

HONEST SCOPE: this encodes the well-established Japanese punctuation convention (。/、), which is
near-universal for Japanese transcription. GoTranscript's FULL Japanese style guide (their specific
Clean/Full Verbatim conventions, name/number handling) is not yet in hand — extend this layer when
those guidelines arrive; the slot is now ready to receive them.
"""
from .ja_rules import japanese_punctuation

JA_GOTRANSCRIPT_SCANNERS = (japanese_punctuation,)
