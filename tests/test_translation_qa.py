"""Offline tests for the per-language translation-QA layer (ROADMAP Phase 8 task 4).

Deterministic, no network, no model. Covers the four required cases plus the honesty laws
(unverifiable never fake-passes; zero false positives on correct text)."""
import pytest

from transcript_truth.translation_qa import (
    run_qa,
    register_translation_layer,
    clear_translation_layers,
    registered_layers,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Every test starts with an empty glossary registry."""
    clear_translation_layers()
    yield
    clear_translation_layers()


# ------------------------------------------------------------------ (a) clean text passes
def test_clean_translation_passes_no_flags():
    src = "El presidente firmo el acuerdo en Madrid el martes por la manana."
    tgt = "The president signed the agreement in Madrid on Tuesday morning."
    r = run_qa(src, tgt, "es", "en")
    assert r["flags"] == []
    assert r["verifiable"] is True
    assert r["ok"] is True
    assert 0.5 <= r["ratio"] <= 1.9


def test_clean_english_paraphrase_passes():
    src = "The quarterly report shows revenue rose sharply across every region."
    tgt = "The quarterly report indicates revenue climbed sharply in all regions."
    r = run_qa(src, tgt, "en", "en")
    assert r["flags"] == []
    assert r["ok"] is True


# ------------------------------------------------------------------ (b) source-script leak
def test_arabic_run_left_in_translation_flags_leak():
    src = "قال المتحدث إن الاجتماع سيعقد في القاهرة."
    tgt = "The spokesman said the meeting will be held in القاهرة."
    r = run_qa(src, tgt, "ar", "en")
    kinds = [f["kind"] for f in r["flags"]]
    assert "source_script_leak" in kinds
    leak = next(f for f in r["flags"] if f["kind"] == "source_script_leak")
    assert "القاهرة" in leak["evidence"]
    assert r["ok"] is False
    # leak is the most-severe flag => reported first
    assert r["flags"][0]["kind"] == "source_script_leak"


def test_devanagari_run_left_in_translation_flags_leak():
    src = "अध्यक्ष ने मुंबई में समझौते पर हस्ताक्षर किए।"
    tgt = "The chairman signed the agreement in मुंबई today."
    r = run_qa(src, tgt, "hi", "en")
    assert any(f["kind"] == "source_script_leak" for f in r["flags"])
    assert r["ok"] is False


def test_native_script_in_nonlatin_target_is_not_a_leak():
    # Translating INTO Japanese: Japanese script is correct output, never a "leak".
    src = "The meeting is in Tokyo."
    tgt = "会議は東京で行われます。"
    r = run_qa(src, tgt, "en", "ja")
    assert all(f["kind"] != "source_script_leak" for f in r["flags"])
    # non-Latin target has no ratio band => cannot be mechanically cleared
    assert r["verifiable"] is False
    assert r["ok"] is False


# ------------------------------------------------------------------ (c) length-ratio
def test_half_length_translation_flags_ratio():
    src = ("El comite examino cuidadosamente cada una de las propuestas presentadas "
           "durante la larga y detallada sesion de la manana antes de emitir su fallo final.")
    tgt = "The committee reviewed the proposals."   # grossly truncated (~0.28x)
    r = run_qa(src, tgt, "es", "en")
    assert r["ratio"] < 0.5
    assert any(f["kind"] == "length_ratio" for f in r["flags"])
    assert r["ok"] is False


def test_nonlatin_target_reports_unverifiable_not_fake_pass():
    # A non-Latin target has no ratio band and no meaningful leak check: clean-looking text
    # must report verifiable=False, NEVER a silent green.
    r = run_qa("Some clean source text here.", "다른 언어로 번역된 문장입니다.", "en", "ko")
    assert r["verifiable"] is False
    assert r["ok"] is False


# ------------------------------------------------------------------ (d) glossary hook
def test_glossary_forces_required_term():
    register_translation_layer("es-en", {"IA": "AI"})
    assert "es-en" in registered_layers()
    src = "El equipo de IA publico un nuevo modelo."
    bad = "The team published a new model."          # dropped the mandated 'AI'
    r = run_qa(src, bad, "es", "en")
    assert any(f["kind"] == "glossary" and f["evidence"] == "AI" for f in r["flags"])
    assert r["ok"] is False

    good = "The AI team released a new model."
    r2 = run_qa(src, good, "es", "en")
    assert all(f["kind"] != "glossary" for f in r2["flags"])
    assert r2["ok"] is True


def test_glossary_pair_normalization_strips_region():
    register_translation_layer(("es", "en"), {"OpenAI": "OpenAI"})
    src = "OpenAI presento su informe."
    bad = "The company presented its report."         # 'OpenAI' rendering lost
    r = run_qa(src, bad, "es-ES", "en-US")            # region subtags must normalize to es-en
    assert any(f["kind"] == "glossary" for f in r["flags"])


def test_glossary_only_fires_when_source_term_present():
    register_translation_layer("es-en", {"IA": "AI"})
    src = "El informe fue aprobado."                  # no 'IA' trigger in source
    tgt = "The report was approved."
    r = run_qa(src, tgt, "es", "en")
    assert all(f["kind"] != "glossary" for f in r["flags"])
    assert r["ok"] is True


# ------------------------------------------------------------------ severity ordering & shape
def test_flags_ordered_most_severe_first():
    register_translation_layer("ar-en", {"مصر": "Egypt"})
    src = ("قال المتحدث الرسمي إن الاجتماع المهم سيعقد غدا في القاهرة في مصر "
           "لمناقشة الاتفاق الجديد بين الدول المشاركة في المؤتمر الدولي الكبير.")
    tgt = "meeting القاهرة"                            # leak + glossary miss + truncation
    r = run_qa(src, tgt, "ar", "en")
    kinds = [f["kind"] for f in r["flags"]]
    assert kinds[0] == "source_script_leak"
    assert "glossary" in kinds and "length_ratio" in kinds
    # leak precedes glossary precedes ratio
    assert kinds.index("source_script_leak") < kinds.index("glossary") < kinds.index("length_ratio")


def test_return_shape_keys():
    r = run_qa("hola", "hello", "es", "en")
    assert set(r.keys()) == {"ok", "verifiable", "flags", "ratio"}
    assert isinstance(r["flags"], list)
    for f in r["flags"]:
        assert set(f.keys()) == {"kind", "evidence", "note"}


# ------------------------------------------------------------ regression: verifier-found defects
# The workflow's adversarial reviewer surfaced these exact failure modes; each is now pinned.

def test_same_script_verbatim_passthrough_is_not_silent_green():
    """es->en (same Latin script) source echoed verbatim must NOT pass — the source-script-leak
    detector is blind to a same-script passthrough, so it is caught as untranslated_passthrough."""
    src = "El comité revisó las propuestas durante la reunión de la mañana."
    r = run_qa(src, src, "es", "en")               # translation == source (untranslated)
    assert any(f["kind"] == "untranslated_passthrough" for f in r["flags"])
    assert r["ok"] is False


def test_genuine_same_script_translation_not_flagged_as_passthrough():
    """A real es->en translation shares almost no exact word forms — no passthrough false positive."""
    src = "El comité revisó las propuestas durante la reunión de la mañana."
    tgt = "The committee reviewed the proposals during the morning meeting."
    r = run_qa(src, tgt, "es", "en")
    assert not any(f["kind"] == "untranslated_passthrough" for f in r["flags"])


def test_glossary_word_boundary_no_false_positive():
    """A glossary term must match on word boundaries: requiring 'EU' must not be satisfied-or-
    triggered by 'Europe'/'queue'. Here the source term 'UE' is present but the required 'EU'
    appears only inside 'queue' — that substring must NOT count as satisfying the requirement."""
    register_translation_layer("es-en", {"UE": "EU"})
    src = "La UE aprobó la medida."
    tgt = "The queue approved the measure."          # 'EU' only inside 'queue' — not the term
    r = run_qa(src, tgt, "es", "en")
    assert any(f["kind"] == "glossary" for f in r["flags"])


def test_parenthetical_citation_of_original_is_not_a_leak():
    """Citing the original script in parentheses is correct practice, not an untranslated leak."""
    src = "Газета Правда опубликовала el informe."
    tgt = "The newspaper Pravda (Газета Правда) published the report."
    r = run_qa(src, tgt, "ru", "en")
    assert not any(f["kind"] == "source_script_leak" for f in r["flags"])
