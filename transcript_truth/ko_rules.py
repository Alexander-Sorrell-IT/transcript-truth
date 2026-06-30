"""Korean deterministic rules. The crown jewel is BATCHIM PARTICLE SELECTION: a Korean particle's
form is fixed by whether the preceding syllable ends in a consonant (batchim) — 은/는, 이/가, 을/를,
과/와, 아/야, (으)로. The CHOICE is pure Unicode arithmetic ((ord(c)-0xAC00)%28), but knowing WHERE a
particle is (vs part of a word like 마을/사과) needs morphology — so we use Kiwi to tag particles (J*),
then apply the batchim rule. Deterministic verdict, model only proposes the segmentation.

Kiwi is imported lazily; if it's not installed the scanner no-ops (non-Korean users aren't affected).
"""
from __future__ import annotations
from .types import Flag, Transcript

_kiwi = None
_kiwi_failed = False

# particle surface form -> (correct_after_batchim, correct_after_vowel)
_RULE = {
    "은": ("은", "는"), "는": ("은", "는"),
    "이": ("이", "가"), "가": ("이", "가"),
    "을": ("을", "를"), "를": ("을", "를"),
    "과": ("과", "와"), "와": ("과", "와"),
    "아": ("아", "야"), "야": ("아", "야"),
}


def _kiwi_inst():
    global _kiwi, _kiwi_failed
    if _kiwi is None and not _kiwi_failed:
        try:
            from kiwipiepy import Kiwi
            _kiwi = Kiwi()
        except Exception:
            _kiwi_failed = True
    return _kiwi


def _jong(syl):
    """Final-consonant (jongseong) index of a Hangul syllable, or None if not Hangul."""
    if "가" <= syl <= "힣":
        return (ord(syl) - 0xAC00) % 28
    return None


import re

_PART_CHARS = set("은는이가을를과와")          # single-syllable batchim particles
_HANGUL_WORD = re.compile(r"[가-힣]+")
_NOUNISH = ("NN", "NR", "NP", "SL", "SH", "SN")  # noun / number / latin / hanja / digit stems


def _is_single_word(kiwi, word):
    """True if Kiwi reads `word` as ONE lexical token (a real word like 마을/사과/차이) rather than
    stem+particle — so we don't mistake a word's final syllable for a wrong particle."""
    toks = kiwi.tokenize(word)
    return len(toks) == 1 and toks[0].tag.startswith(_NOUNISH)


def _stem_is_noun(kiwi, stem):
    toks = kiwi.tokenize(stem)
    return bool(toks) and toks[-1].tag.startswith(_NOUNISH)


def _flag(prev_syl, word, correct, ln, directional=False):
    kind = "Directional particle" if directional else "Particle"
    note = ("Use 로 after a vowel or ㄹ; 으로 after any other final consonant."
            if directional else "Choose the particle by the previous syllable's batchim.")
    return Flag(rule="ko_particle", line=ln, severity="minor", evidence=word,
                label=f"{kind} is wrong after '{prev_syl}' — use '{correct}'", fix=note)


def korean_particles(t: Transcript) -> list[Flag]:
    """Surface-split particle check, guarded by Kiwi so real words don't false-fire:
    a Hangul word ending in a particle is split; if the whole word is a single known noun
    (마을, 차이) it's skipped; otherwise, when the stem is a noun, the batchim rule decides the
    correct particle and a mismatch is flagged. Catches all six pairs (incl. 은/는, 이/가 that a
    pure morphological parse re-routes to a verb on ungrammatical input)."""
    kiwi = _kiwi_inst()
    if kiwi is None:
        return []
    out: list[Flag] = []
    for ln in t.lines:
        for word in _HANGUL_WORD.findall(ln.text):
            if len(word) < 2 or _is_single_word(kiwi, word):
                continue
            # directional (으)로 first (2-syllable form)
            if word.endswith("으로") or (word.endswith("로") and len(word) >= 2):
                form = "으로" if word.endswith("으로") else "로"
                stem = word[:-len(form)]
                if stem and _stem_is_noun(kiwi, stem):
                    jong = _jong(stem[-1])
                    if jong is not None:
                        want = "로" if (jong == 0 or jong == 8) else "으로"
                        if form != want:
                            out.append(_flag(stem[-1], word, want, ln.n, directional=True))
                if word.endswith("으로") or form == "로":
                    continue
            part = word[-1]
            if part not in _PART_CHARS:
                continue
            stem = word[:-1]
            if not stem or not _stem_is_noun(kiwi, stem):
                continue
            jong = _jong(stem[-1])
            if jong is None:
                continue
            correct = _RULE[part][0] if jong != 0 else _RULE[part][1]
            if part != correct:
                out.append(_flag(stem[-1], word, correct, ln.n))
    return out
