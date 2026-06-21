"""Legal as a CROSS-LANGUAGE style, composed (style × language).

The insight: a style guide is two things glued together —
  1. language-AGNOSTIC formatting rules  (timestamps, spacing, bracket tags, no
     accented letters) — identical whatever the language is, and
  2. language-SPECIFIC checks            (English CVL spelling; Japanese kana-rule
     and homophones; Spanish stress/diacritics).

So `legal` = LEGAL_CORE (agnostic) + the chosen language's own checks. That makes
`legal:ja`, `legal:es`, `legal:en` all real profiles from the same spine. Existing
single profiles (`default`, `legal`, `me`) are untouched — this is additive.

Adding a language = drop its data in data/ + add one row to LANG below. Plugin-style,
exactly like the rest of the engine.
"""
from ._base import Profile, register
from ..scanners import (timestamps, fillers, context_homophones,
                        no_exclamation, terminal_punctuation)
from ..kana_rules import kana_usage
from ..legal_rules import (legal_spacing, legal_tags, legal_accents,
                           LEGAL_SCANNERS, LEGAL_FIXERS)

# language-agnostic LEGAL formatting core — applies to ANY language
LEGAL_CORE = (timestamps, legal_spacing, legal_tags, legal_accents)

# per-language checks (the language's own correctness layer) + that language's fixers
LANG = {
    # English legal = the full TranscribeMe CVL set (already includes the core rules)
    "en": {"scanners": (timestamps, *LEGAL_SCANNERS), "fixers": tuple(LEGAL_FIXERS), "core": False},
    # Japanese legal = agnostic legal core + Japanese-language verification
    "ja": {"scanners": (kana_usage, fillers, context_homophones,
                        no_exclamation, terminal_punctuation), "fixers": (), "core": True},
    # Spanish legal = agnostic core for now; ES-specific scanners (stress/diacritics) pending
    "es": {"scanners": (), "fixers": (), "core": True},
}

_DESC = {"en": "English (TranscribeMe CVL)", "ja": "Japanese", "es": "Spanish"}

for _lang, _cfg in LANG.items():
    _scanners = ((*LEGAL_CORE, *_cfg["scanners"]) if _cfg["core"] else _cfg["scanners"])
    register(Profile(
        name=f"legal:{_lang}",
        description=f"Legal style — {_DESC[_lang]} (cross-language composition)",
        scanners=_scanners,
        fixers=_cfg["fixers"],
        default_mode="clean_verbatim",
    ))
