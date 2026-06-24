"""Spanish profiles. Base = authority lexicon check (pyspellchecker via lexicon.py).
:full adds the existing accent-aware homophone surfacer + the generic collocation
decision layer (Leipzig-grounded)."""
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..es_rules import homophone_traps

# NOTE: the collocation decision layer is intentionally NOT used for Spanish — es
# confusables are grammatical homophones (haya/halla), separated by syntax not
# collocation, so decision misfires (measured 26% false-positive). Those route to
# the coherence/syntax layer instead. Decision stays for ru/uk paronyms (3% FP).
register(Profile(
    name="es",
    description="Spanish — authority lexicon check (pyspellchecker + wordfreq)",
    scanners=(make_unknown_word("es", "latin"),),
    default_mode="clean_verbatim",
))
register(Profile(
    name="es:full",
    description="Spanish — base + accent-aware homophone surfacer (review)",
    scanners=(make_unknown_word("es", "latin"), homophone_traps),
    default_mode="clean_verbatim",
))
