"""Spanish name surfacer — phonetic candidate matching + low-FP scanner gate."""
from transcript_truth import es_names as en
from transcript_truth.types import Transcript, Line


def test_phonetic_key_collapses_spanish_equivalents():
    assert en.phonetic_key("Selma") == en.phonetic_key("Zelma")   # z == s (seseo)
    assert en.phonetic_key("Vasco") == en.phonetic_key("Basco")   # b == v
    assert en.phonetic_key("Hugo") == en.phonetic_key("ugo")      # silent h


def test_heard_impression_surfaces_real_name():
    # the 'Selma' case: a human's phonetic impression -> real given names, top of list
    names = [n for n, _ in en.candidates("sema", n=3)]
    assert "Selma" in names


def test_known_names_recognised():
    for n in ["Natali", "Yamir", "Josue", "Humbert", "Tony", "Leti"]:
        assert en.is_name(n)


def test_scanner_fires_on_garble_not_on_common_words():
    sc = en.make_name_surfacer("es")
    t = Transcript(lines=[Line(1, "Hola, Selba, soy Leti. Oye, prima, hablame.")])
    flags = sc(t)
    ev = [f.evidence for f in flags]
    assert "Selba" in ev                       # the out-of-vocab name garble fires
    assert "soy" not in ev and "Oye" not in ev  # common words do not (freq gate)
    assert "prima" not in ev                    # real word does not


def test_scanner_quiet_on_clean_text():
    sc = en.make_name_surfacer("es")
    t = Transcript(lines=[Line(1, "Esta experiencia le permite replicar y adaptar el modelo.")])
    assert sc(t) == []
