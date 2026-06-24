"""English profiles. Base = authority lexicon check (pyspellchecker via lexicon.py).
:full adds the homophone surfacer (from en_confirmed.json) + the generic collocation
decision layer."""
from ._base import Profile, register
from ..lexicon import make_unknown_word, make_confusables

# NOTE: like Spanish, English confusables are grammatical homophones (there/their,
# by/buy) — syntax-separated, not collocation-separated — so the decision layer
# misfires here and is intentionally excluded; they route to the coherence/syntax
# layer. The surfacer flags them for review.
register(Profile(
    name="en",
    description="English — authority lexicon check (pyspellchecker + wordfreq)",
    scanners=(make_unknown_word("en", "latin"),),
    default_mode="clean_verbatim",
))
register(Profile(
    name="en:full",
    description="English — base + homophone surfacer (review)",
    scanners=(make_unknown_word("en", "latin"), make_confusables("en", "latin")),
    default_mode="clean_verbatim",
))
