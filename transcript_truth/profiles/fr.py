"""French profiles. Base = Latin authority lexicon check (pyspellchecker + wordfreq, via
lexicon.py) + French typography spacing (fr_rules). :full adds the generic collocation/coherence
layer. Same plug-in shape as es/en — drops in and auto-registers; the Phase-2 router activates it
automatically when audio detects as 'fr'."""
from ._base import Profile, register
from ..lexicon import make_unknown_word
from ..fr_rules import french_spacing
from ..coherence_ml import make_coherence

register(Profile(
    name="fr",
    description="French — authority lexicon check (pyspellchecker + wordfreq) + French spacing typography",
    scanners=(make_unknown_word("fr", "latin"), french_spacing),
    default_mode="clean_verbatim",
))
register(Profile(
    name="fr:full",
    description="French — base + LLM coherence (review; needs network)",
    scanners=(make_unknown_word("fr", "latin"), french_spacing, make_coherence("fr", "latin")),
    default_mode="clean_verbatim",
))
