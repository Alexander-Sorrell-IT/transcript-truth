"""Translation verdict layer — every case here is a CONFIRMED defect from the 2026-07-11
adversarial review workflow (3 attack lenses, 14 findings), pinned so it can't regress."""
from transcript_truth.translate import survival_checks, agreement, _pick_primary, _latin_names
from transcript_truth.numparse import values, spelled_support


# --- numbers: language-aware VALUES, not English strings -------------------------------------

def test_spelled_source_numbers_are_visible():
    # v1 CRITICAL: 'doce mil' was invisible -> wrong translation passed ok=True
    c = survival_checks("doce mil dolares", "twenty thousand dollars", "es", "en")
    assert not c["ok"] and 12000 in c["missing_numbers"] and 20000 in c["introduced_numbers"]
    ok = survival_checks("doce mil dolares", "twelve thousand dollars", "es", "en")
    assert ok["ok"] and ok["passed"] == ok["total"] == 1


def test_locale_decimal_comma_not_mangled():
    # v1 HIGH: 'es sind 2,5 prozent' became 25 -> faithful 2.5 flagged, wrong 25 passed
    assert survival_checks("es sind 2,5 prozent", "it is 2.5 percent", "de", "en")["ok"]
    assert not survival_checks("es sind 2,5 prozent", "it is 25 percent", "de", "en")["ok"]


def test_eu_thousands_dot():
    # v1 HIGH: '12.000 euro' (de) = twelve thousand, not 12.0
    assert survival_checks("das kostet 12.000 euro", "that costs 12,000 euros", "de", "en")["ok"]


def test_duplicate_numbers_multiset():
    # v1 HIGH: '5 cats and 5 dogs' vs '5 cats and 3 dogs' passed via set collapse
    c = survival_checks("5 cats and 5 dogs", "5 cats and 3 dogs", "en", "en")
    assert not c["ok"] and 5 in c["missing_numbers"] and 3 in c["introduced_numbers"]


def test_spelled_target_numbers_accepted():
    # v1 HIGH: faithful non-English target spelling numbers was falsely flagged
    assert survival_checks("the price is 12 dollars", "el precio es doce dolares", "en", "es")["ok"]


def test_decade_years_never_wrong_single_value():
    # v1: word2number turned 'nineteen ninety-five' into a silent wrong value
    assert dict(values("back in nineteen ninety-five", "en")) == {19: 1, 95: 1}


def test_hi_ur_report_unverifiable_not_fake_pass():
    assert not spelled_support("hi") and not spelled_support("ur")
    c = survival_checks("kuch text", "some text", "hi", "en")
    assert c["numbers_verifiable"] is False


# --- names: folded, word-boundary, frequency-floored ------------------------------------------

def test_diacritic_folded_name_survival():
    # v1 HIGH: 'Bergstrom' in translation failed 'Bergström' in source
    c = survival_checks("Bergström besuchte Ljubljana", "Bergstrom visited Ljubljana", "de", "en")
    assert c["missing_names"] == []


def test_substring_never_satisfies_name():
    # v1 HIGH: substring containment false-passed dropped names ('india' in 'indiana')
    c = survival_checks("Kowalski met Nakamura", "He met Nakamura at the Kowalskiville fair", "en", "en")
    assert "Kowalski" in c["missing_names"] and "Nakamura" not in c["missing_names"]


def test_common_words_not_demanded_as_names():
    # v1 HIGH: gazetteer junk ('Buenos', 'White') was demanded verbatim of good translations
    assert survival_checks("Buenos dias a todos", "Good morning everyone", "es", "en")["ok"]


def test_accented_and_unambiguous_names_detected():
    # accented initials work; lexicon-word names (Rome, Ali, Rio, even Nguyen — wordlists carry
    # common surnames) are deliberately NOT demanded mechanically — the cross-witness agreement
    # control covers those; the mechanical check demands only unambiguous names
    names = _latin_names("Ali met Álvaro and Nguyen in Rio near Bergström", "en")
    assert {"Álvaro", "Bergström"} <= names
    assert "Rio" not in names and "Ali" not in names


def test_non_latin_source_reports_names_unverifiable():
    # v1 HIGH: Arabic-script source made the name check silently vacuous
    c = survival_checks("سافر محمد إلى باريس أمس", "Mohammed traveled to Paris", "ar", "en")
    assert c["names_verifiable"] is False


# --- agreement + primary pick ------------------------------------------------------------------

def test_agreement_ignores_punctuation_and_number_format():
    # v1: punctuation + digit/spelled formatting counted as disagreement
    a = agreement("Seventeen people died.", "17 people died", "en")
    assert a > 0.9


def test_primary_tie_goes_to_transcript_witness_not_shorter():
    # v1 CRITICAL: (passed, -len) tuple let a truncated witness win ties
    c_full = {"ok": True, "passed": 0, "total": 0}
    c_trunc = {"ok": True, "passed": 0, "total": 0}
    primary, _, alt, _ = _pick_primary("The meeting on Tuesday covered the budget in detail",
                                       c_full, "The meeting", c_trunc)
    assert primary.startswith("The meeting on Tuesday")
