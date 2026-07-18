"""Japanese profile — its OWN registered language identity (no longer riding `default`).

The deterministic crown jewel is `kana_usage` (kana_rules): GoTranscript guideline rule 24 —
formal nouns (訳→わけ, 事→こと, 為→ため) and faded auxiliaries (下さい→ください, 見る→みる after て/で)
must be written in kana, decided GRAMMATICALLY via Sudachi so real words (翻訳, 事件, 映画を見る) never
false-fire. No model in the verdict path.

Japanese OUTPUT-FORMAT rules (punctuation 。/、) live in the site layer (`gotranscript_ja_rules`) and
compose in for GoTranscript jobs. Auto-registers; the Phase-2 router activates it when audio detects
as 'ja' (language.PROFILE_FOR now maps ja→ja). `ja:full` reserves the pitch-accent homophone layer
(pitch_accent) for the deeper coherence pass.
"""
from ._base import Profile, register
from ..kana_rules import kana_usage

register(Profile(
    name="ja",
    description="Japanese — kana-usage (GoTranscript rule 24, Sudachi-grammatical); no model in verdict",
    scanners=(kana_usage,),
    default_mode="clean_verbatim",
    aliases=("jp",),
))
register(Profile(
    name="ja:full",
    description="Japanese — kana-usage + (pitch-accent homophone layer available via pitch_accent)",
    scanners=(kana_usage,),
    default_mode="clean_verbatim",
))
