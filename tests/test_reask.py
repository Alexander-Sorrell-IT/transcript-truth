"""Re-ask loop (PERFECTION_PLAN III.1) — the deterministic halves, no API/audio needed."""
from transcript_truth.reask import _slot_word, _variants_at, _plausible, _known, reask_contested


TOKS = "White Hernandez 1 Nisan'da Valparaíso'dan gitti".split()


def test_slot_word_alignment():
    # fresh read proposes a word for the contested position by neighborhood alignment
    assert _slot_word("Bay Fernandez 1 Nisan'da", TOKS, 1) == "Fernandez"
    # a completely unrelated read abstains (None), never guesses
    assert _slot_word("tamamen farkli bir cumle burada simdi", TOKS, 1) is None
    assert _slot_word("", TOKS, 1) is None


def test_variants_collects_witness_words_at_position():
    reads = {"a": "Bay Fernandez 1 Nisan'da Valparaíso'dan gitti",
             "b": "White Hernandez 1 Nisan'da Valparaíso'dan gitti"}
    v = _variants_at(reads, TOKS, 0)
    assert "Bay" in v and "White" in v


def test_plausible_promotes_known_or_witnessed_never_invents():
    assert _plausible("Fernandez", {"Hernandez"}, "tr")     # gazetteer name
    assert _plausible("Bay", {"Bay", "White"}, "tr")        # existing witness variant
    assert not _plausible("Xqzvv", {"Hernandez"}, "tr")     # free invention -> rejected


def test_known_rank():
    assert _known("Yamamoto", "tr")                          # gazetteer name
    assert not _known("Yamanoto", "tr")                      # garble — the downgrade guard's basis


def test_reask_no_spans_is_identity(tmp_path):
    res = {"text": "hello world", "uncertain_spans": []}
    out = reask_contested(str(tmp_path / "missing.wav"), {}, "en", res)
    assert out["text"] == "hello world"
