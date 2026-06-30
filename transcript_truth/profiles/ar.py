"""Arabic profile. Base = authority lexicon (pyspellchecker ar + wordfreq) + tatweel removal +
Latin-leak check. :full adds coherence. Auto-registers; Phase-2 router activates on detected 'ar'.
NOTE: witness ASR quality for Arabic (dialect/diacritics) is not yet battery-validated — Phase 5
'specialized model' evaluation is pending; the deterministic profile is ready regardless."""
import re
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..script_rules import tatweel, make_latin_leak
from ..coherence_ml import make_coherence

_AR = re.compile(r"[؀-ۿ]")

register(Profile(
    name="ar",
    description="Arabic — authority lexicon check + tatweel (kashida) removal + Latin-leak",
    scanners=(make_unknown_word("ar", "latin"), tatweel, make_latin_leak(_AR, "Arabic")),
    default_mode="clean_verbatim",
))
register(Profile(
    name="ar:full",
    description="Arabic — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("ar", "latin"), tatweel, make_latin_leak(_AR, "Arabic"),
              make_coherence("ar", "latin")),
    default_mode="clean_verbatim",
))
