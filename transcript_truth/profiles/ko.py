"""Korean profile. The deterministic crown jewel is the BATCHIM PARTICLE check (ko_rules):
a particle's form (은/는, 이/가, 을/를, 과/와, (으)로) is fixed by the previous syllable's final
consonant — pure Unicode arithmetic for the verdict, with Kiwi morphology only to locate particles
(so real words like 마을/차이 don't false-fire). No model in the verdict path.

(The Latin-lexicon authority check isn't used here — Korean needs mecab_ko_dic for wordfreq, not
installed; the Sino-Korean homophone layer is the future ko:full add via Kiwi.) Auto-registers; the
Phase-2 router activates it when audio detects as 'ko'."""
from ._base import Profile, register
from ..ko_rules import korean_particles

register(Profile(
    name="ko",
    description="Korean — batchim particle check (은/는·이/가·을/를·과/와·(으)로) via Kiwi; no model in verdict",
    scanners=(korean_particles,),
    default_mode="clean_verbatim",
))
register(Profile(
    name="ko:full",
    description="Korean — base (Sino-Korean homophone layer TODO)",
    scanners=(korean_particles,),
    default_mode="clean_verbatim",
    aliases=("kr",),
))
