"""Turkish profiles. Base = wordfreq-only authority check (Turkish isn't in pyspellchecker, so
the lexicon degrades to a frequency escape) + the q/w/x foreign-letter check (tr_rules). :full adds
the generic coherence layer. Auto-registers; the Phase-2 router activates it when audio detects 'tr'."""
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..tr_rules import turkish_foreign_letters
from ..coherence_ml import make_coherence

register(Profile(
    name="tr",
    description="Turkish — wordfreq authority check + q/w/x foreign-letter rule",
    scanners=(make_unknown_word("tr", "latin"), turkish_foreign_letters),
    default_mode="clean_verbatim",
))
register(Profile(
    name="tr:full",
    description="Turkish — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("tr", "latin"), turkish_foreign_letters, make_coherence("tr", "latin")),
    default_mode="clean_verbatim",
))
