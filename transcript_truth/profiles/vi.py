"""Vietnamese profiles. Base = Latin authority lexicon check (wordfreq — pyspellchecker lacks vi,
so it degrades to a frequency escape) + the f/j/w/z foreign-letter check (vi_rules). :full adds the
generic coherence layer. Auto-registers; the Phase-2 router activates it when audio detects 'vi'."""
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..vi_rules import vietnamese_foreign_letters
from ..coherence_ml import make_coherence

register(Profile(
    name="vi",
    description="Vietnamese — wordfreq authority check + f/j/w/z foreign-letter rule",
    scanners=(make_unknown_word("vi", "latin"), vietnamese_foreign_letters),
    default_mode="clean_verbatim",
))
register(Profile(
    name="vi:full",
    description="Vietnamese — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("vi", "latin"), vietnamese_foreign_letters, make_coherence("vi", "latin")),
    default_mode="clean_verbatim",
))
