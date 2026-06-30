"""German profiles. Base = Latin authority lexicon check + pre-1996 ß spelling check (de_rules).
:full adds the generic coherence layer. Same plug-in shape as es/en/fr — auto-registers; the
Phase-2 router activates it when audio detects as 'de'."""
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..de_rules import german_old_spelling
from ..coherence_ml import make_coherence

register(Profile(
    name="de",
    description="German — authority lexicon check (pyspellchecker + wordfreq) + pre-1996 ß spelling",
    scanners=(make_unknown_word("de", "latin"), german_old_spelling),
    default_mode="clean_verbatim",
))
register(Profile(
    name="de:full",
    description="German — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("de", "latin"), german_old_spelling, make_coherence("de", "latin")),
    default_mode="clean_verbatim",
))
