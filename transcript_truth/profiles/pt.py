"""Portuguese profiles. Base = Latin authority lexicon check + cedilla-before-e/i check (pt_rules).
:full adds the generic coherence layer. Auto-registers; the Phase-2 router activates it when audio
detects as 'pt'."""
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..pt_rules import portuguese_cedilla
from ..coherence_ml import make_coherence

register(Profile(
    name="pt",
    description="Portuguese — authority lexicon check (pyspellchecker + wordfreq) + cedilla rule",
    scanners=(make_unknown_word("pt", "latin"), portuguese_cedilla),
    default_mode="clean_verbatim",
))
register(Profile(
    name="pt:full",
    description="Portuguese — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("pt", "latin"), portuguese_cedilla, make_coherence("pt", "latin")),
    default_mode="clean_verbatim",
))
