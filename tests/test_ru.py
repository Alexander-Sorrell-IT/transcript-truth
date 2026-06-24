"""Russian/Ukrainian Cyrillic plugin tests.

Covers the three layers:
  1. cyrillic mixed-script homoglyph  -> HARD (moderate) error, authority-free
  2. OpenCorpora lexicon check        -> REVIEW (out-of-dictionary surfacer)
  3. confusable/paronym surfacer      -> REVIEW, opt-in (:full only), data-backed
and locks that the graded base profile never fires on clean text.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.types import Transcript, Line
from transcript_truth.cyrillic_rules import mixed_script
from transcript_truth.ru_rules import make_unknown_word, make_confusables
from transcript_truth.profiles import _base
import transcript_truth.profiles.ru  # register

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _t(text):
    return Transcript(lines=[Line(1, text)])


def test_homoglyph_is_hard_error():
    # Latin 'o' inside a Cyrillic word
    flags = mixed_script(_t("Рoссия большая страна."))
    assert any(f.rule == "cyrillic_mixed_script" and f.severity == "moderate" for f in flags)


def test_clean_cyrillic_no_homoglyph():
    assert mixed_script(_t("Россия большая страна.")) == []


def test_allcaps_latin_word_not_flagged():
    # a genuine all-Latin token in a Russian line is not a homoglyph
    assert mixed_script(_t("Купил новый iPhone сегодня.")) == []


def test_unknown_word_is_review():
    ru_unknown = make_unknown_word("ru")
    flags = ru_unknown(_t("Он сказал асдфыв вчера."))
    assert any(f.rule == "ru_unknown_word" and f.severity == "review" for f in flags)


def test_known_words_and_names_not_flagged():
    ru_unknown = make_unknown_word("ru")
    assert ru_unknown(_t("Это компания и кампания.")) == []
    assert ru_unknown(_t("Привет, Москва!")) == []


def test_confusable_surfacer_is_review_and_fires():
    ru_conf = make_confusables("ru")
    flags = ru_conf(_t("Рекламная кампания нашей компании."))
    assert flags and all(f.severity == "review" for f in flags)
    assert any(f.rule == "ru_confusable" for f in flags)


def test_profiles_registered():
    for n in ("ru", "uk", "ua", "ru:full", "uk:full"):
        assert _base.get(n)


def test_base_profile_excludes_confusables():
    # the blanket confusable surfacer must stay opt-in (:full), never in graded base
    rules = {s.__name__ for s in _base.get("ru").scanners}
    assert "ru_confusable" not in rules
    assert "ru_confusable" in {s.__name__ for s in _base.get("ru:full").scanners}


def test_data_files_grounded_and_nonempty():
    for lang, lo in (("ru", 200), ("uk", 100)):
        data = json.load(open(os.path.join(_HERE, "data", f"{lang}_confirmed.json"), encoding="utf-8"))
        assert len(data) >= lo, f"{lang}: only {len(data)} sets"
        for e in data:                       # every set has >= 2 options
            assert len(e.get("options", [])) >= 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
