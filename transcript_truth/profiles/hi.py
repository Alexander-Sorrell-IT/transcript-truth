"""Hindi profile (Devanagari). Base = wordfreq authority check (pyspellchecker lacks hi) +
Latin-leak check. :full adds coherence. Auto-registers; Phase-2 router activates on detected 'hi'.
NOTE: witness ASR quality for Hindi not yet battery-validated (Phase 5 model evaluation pending)."""
import re
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..script_rules import make_latin_leak
from ..coherence_ml import make_coherence

_DEVA = re.compile(r"[ऀ-ॿ]")

register(Profile(
    name="hi",
    description="Hindi — wordfreq authority check + Latin-leak (Devanagari)",
    scanners=(make_unknown_word("hi", "latin"), make_latin_leak(_DEVA, "Hindi")),
    default_mode="clean_verbatim",
))
register(Profile(
    name="hi:full",
    description="Hindi — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("hi", "latin"), make_latin_leak(_DEVA, "Hindi"),
              make_coherence("hi", "latin")),
    default_mode="clean_verbatim",
))
