"""Spanish profiles. Base = authority lexicon check (pyspellchecker via lexicon.py).
:full adds the existing accent-aware homophone surfacer + the generic collocation
decision layer (Leipzig-grounded)."""
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..es_rules import homophone_traps
from ..es_names import make_name_surfacer
from ..coherence_ml import make_coherence

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
    description="Spanish — base + homophone surfacer + name surfacer + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("es", "latin"), homophone_traps,
              make_name_surfacer("es"), make_coherence("es", "latin")),
    default_mode="clean_verbatim",
))
