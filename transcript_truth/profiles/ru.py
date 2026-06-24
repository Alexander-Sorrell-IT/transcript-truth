"""Russian language profile (Cyrillic).

Layer 1: deterministic Cyrillic script-integrity (homoglyph catcher), shared with
every Cyrillic language. Per-language confusable surfacers (ться/тся, е/ё …) are
review-tier and load from data/ru_confirmed.json once curated — added next.
"""
from ._base import Profile, register
from ..cyrillic_rules import mixed_script
from ..ru_rules import make_unknown_word, make_confusables
from ..decision import make_decision
from ..coherence_ml import make_coherence

# Base (graded): hard homoglyph error + review-tier out-of-lexicon surfacer.
register(Profile(
    name="ru",
    description="Russian — Cyrillic homoglyph (hard) + OpenCorpora lexicon check (review)",
    scanners=(mixed_script, make_unknown_word("ru")),
    default_mode="clean_verbatim",
))
register(Profile(
    name="uk",
    description="Ukrainian — Cyrillic homoglyph (hard) + OpenCorpora lexicon check (review)",
    scanners=(mixed_script, make_unknown_word("uk")),
    default_mode="clean_verbatim",
    aliases=("ua",),
))

# :full adds the opt-in confusable/paronym surfacer (review-tier, fires on correct
# lines too — like the Spanish surfacer, so it's deliberately NOT in the graded base).
register(Profile(
    name="ru:full",
    description="Russian — base + surfacer + collocation decision + LLM coherence (review)",
    scanners=(mixed_script, make_unknown_word("ru"), make_confusables("ru"),
              make_decision("ru", "cyrillic"), make_coherence("ru", "cyrillic")),
    default_mode="clean_verbatim",
))
register(Profile(
    name="uk:full",
    description="Ukrainian — base + surfacer + collocation decision + LLM coherence (review)",
    scanners=(mixed_script, make_unknown_word("uk"), make_confusables("uk"),
              make_decision("uk", "cyrillic"), make_coherence("uk", "cyrillic")),
    default_mode="clean_verbatim",
))
