"""Per-language PARITY for the deterministic adjudicator — proof, not assertion.

For every supported language the judge must: (1) pick a real word/name over pure garble that
appears nowhere (override, confidence >= 1.0), and (2) DEFER between two real words (confidence
0.0 — never rewrite one valid word into another). Validity comes from each language's lexicon
backend; proper-noun recognition from wordfreq (Latin/Cyrillic/Arabic/Devanagari/Hangul) or the
native JMdict/JMnedict gazetteer (Japanese). Fixes verified here: Turkish İ casefolding, Korean
mecab tokenization, Japanese native gazetteer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from transcript_truth.adjudicate import adjudicate

# lang -> (real_word_A, real_word_B, garble-that-appears-nowhere)
CASES = {
    "en": ("quarterly", "division", "qwzxvbnk"),
    "es": ("ministerio", "gobierno", "qwzxvbnk"),
    "fr": ("gouvernement", "ministre", "qwzxvbnk"),
    "de": ("Regierung", "Minister", "qwzxvbnk"),
    "pt": ("governo", "ministro", "qwzxvbnk"),
    "tr": ("hükümet", "bakan", "qwzxvbnk"),          # İ casefolding path
    "ru": ("правительство", "министр", "фыжщывдл"),
    "uk": ("уряд", "міністр", "фыжщывдл"),
    "ko": ("정부", "장관", "ㅃㅉㄸㄲ"),               # mecab_ko_dic path
    "vi": ("chính", "phủ", "qwzxvbnk"),
    "ar": ("حكومة", "وزير", "قثقثقثظ"),
    "hi": ("सरकार", "मंत्री", "कखगघङछ"),
    "ur": ("حکومت", "وزیر", "قثقثقثظ"),
    "ja": ("政府", "東京", "あqwxzk"),               # JMdict/JMnedict path
}


@pytest.mark.parametrize("lang", list(CASES))
def test_real_word_beats_pure_garble(lang):
    a, _, garble = CASES[lang]
    best, conf = adjudicate([garble, a], [], lang)
    assert best == a and conf >= 1.0, f"{lang}: expected {a!r} to beat garble, got {best!r} conf={conf}"


@pytest.mark.parametrize("lang", list(CASES))
def test_two_real_words_defer(lang):
    a, b, _ = CASES[lang]
    _, conf = adjudicate([a, b], [], lang)
    assert conf == 0.0, f"{lang}: two real words must defer (conf 0), got {conf}"
