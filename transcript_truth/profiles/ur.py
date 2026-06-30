"""Urdu profile (Arabic/Nastaliq script). Base = wordfreq authority check (pyspellchecker lacks ur)
+ tatweel removal + Latin-leak check. :full adds coherence. Auto-registers; Phase-2 router activates
on detected 'ur'. NOTE: witness ASR quality for Urdu not yet battery-validated (Phase 5 pending)."""
import re
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..script_rules import tatweel, make_latin_leak
from ..coherence_ml import make_coherence

_UR = re.compile(r"[؀-ۿ]")

register(Profile(
    name="ur",
    description="Urdu — wordfreq authority check + tatweel removal + Latin-leak",
    scanners=(make_unknown_word("ur", "latin"), tatweel, make_latin_leak(_UR, "Urdu")),
    default_mode="clean_verbatim",
))
register(Profile(
    name="ur:full",
    description="Urdu — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("ur", "latin"), tatweel, make_latin_leak(_UR, "Urdu"),
              make_coherence("ur", "latin")),
    default_mode="clean_verbatim",
))
