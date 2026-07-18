"""Non-Latin-script proper-NAME survival (ROADMAP Phase 8, Builder A) — OFFLINE ONLY.

No model loads, no network, no API. The reliable-path tests inject a plain-string fake
romanizer + identifier via monkeypatch (the design sanctions this — "machinery complete and
unit-tested" until a real romanizer+identifier pair lands). The real-path tests use NO monkeypatch
and document the honest SHIPPED behaviour: under the current install every non-Latin source reports
verifiable=False (never a fake pass), and the cross-witness agreement control owns those clips.

Engine laws asserted here: an UNVERIFIABLE check reports verifiable=False and NEVER passes silently;
ZERO false positives on a correct translation matters more than catching every drop.
"""
import transcript_truth.translit as T
from transcript_truth.translate import survival_checks


# a plain-string stand-in for camel_tools/pykakasi/indic — deterministic, no lib load.
# Values mirror what a real romanizer emits (ar2bw is vowel-less: محمد -> 'mHmd').
_FAKE_ROMAN = {
    "محمد": "mHmd",       # Muhammad  (Arabic, vowel-less skeleton)
    "أحمد": "Ahmd",       # Ahmed
    "القاهرة": "AlqAhrp",  # (place, unused in survives-tests — exonym drift is expected)
    "राजेश": "raajesh",   # Rajesh    (Hindi)
    "प्रिया": "priyaa",   # Priya
}


def _make_reliable(monkeypatch, lang):
    """Turn `lang` into a genuinely-reliable source language for the duration of a test by
    injecting a faithful fake romanizer + identifier and whitelisting it. This exercises the REAL
    name_survival_translit / _skeleton_match pipeline — only the two external deps are faked."""
    monkeypatch.setattr(T, "NAME_VERIFIABLE_LANGS", {lang})
    monkeypatch.setattr(T, "_romanizer", lambda l: (lambda tok: _FAKE_ROMAN.get(tok, "")))
    monkeypatch.setattr(T, "_identifier", lambda l: (lambda tok: tok in _FAKE_ROMAN))


# --- consonant-skeleton matcher (pure unit, no deps) ------------------------------------------

def test_skeleton_bridges_vowelless_romanization():
    # the crux: a vowel-less Arabic romanization must equal the vowelized English by skeleton
    assert T._skeleton("mHmd") == T._skeleton("Muhammad") == "mhmd"
    assert T._skeleton("raajesh") == T._skeleton("Rajesh") == "rjsh"


def test_skeleton_match_high_precision():
    assert T._skeleton_match("mHmd", "Muhammad went to work")
    assert not T._skeleton_match("mHmd", "Ahmed went to work")   # different name, no false match
    # too-short skeleton is treated as unmatchable rather than risk a collision
    assert not T._skeleton_match("a", "a lot of text here")


# --- (a) correct transliteration SURVIVES (no flag) — reliable path ---------------------------

def test_arabic_personal_name_survives(monkeypatch):
    _make_reliable(monkeypatch, "ar")
    r = T.name_survival_translit("محمد ذهب إلى العمل", "Muhammad went to work", "ar")
    assert r["verifiable"] is True
    assert r["checked"] == ["mHmd"]
    assert r["missing_names"] == []          # correctly transliterated -> survives, no flag


def test_hindi_personal_name_survives(monkeypatch):
    _make_reliable(monkeypatch, "hi")
    r = T.name_survival_translit("राजेश आज आया", "Rajesh arrived today", "hi")
    assert r["verifiable"] is True
    assert r["missing_names"] == []


# --- (b) a mangled / dropped name is FLAGGED missing — reliable path --------------------------

def test_dropped_name_is_flagged(monkeypatch):
    _make_reliable(monkeypatch, "ar")
    r = T.name_survival_translit("محمد ذهب", "Ahmed went", "ar")   # wrong name in translation
    assert r["verifiable"] is True
    assert "mHmd" in r["missing_names"]       # Muhammad did NOT survive -> flagged


# --- (c) untransliterable / unreliable => verifiable=False, NOT a pass — REAL path (no fake) --

def test_real_arabic_reports_unverifiable_not_pass():
    # SHIPPED behaviour: ar has a romanizer (camel_tools) but no trustworthy identifier and is not
    # whitelisted -> verifiable=False. The honest "never a fake pass" signal is the verifiable bool.
    r = T.name_survival_translit("محمد ذهب إلى العمل", "Muhammad went to work", "ar")
    assert r["verifiable"] is False
    assert r["missing_names"] == [] and r["checked"] == []


def test_real_japanese_reports_unverifiable():
    # ja's faithful romanizer (pykakasi) is not installed; unidecode reads Han as Chinese, so we
    # refuse rather than emit a confidently-wrong romanization -> verifiable=False.
    assert T._romanizer("ja") is None
    r = T.name_survival_translit("田中さんが東京へ行った", "Mr Tanaka went to Tokyo", "ja")
    assert r["verifiable"] is False


def test_non_latin_target_guard(monkeypatch):
    # even with a reliable source, a NON-Latin target makes the romanized comparison meaningless
    _make_reliable(monkeypatch, "ar")
    r = T.name_survival_translit("محمد ذهب", "محمد ذهب إلى العمل", "ar")
    assert r["verifiable"] is False


# --- (d) ZERO false positives on a clean translation with common words ------------------------

def test_no_false_positive_on_common_words(monkeypatch):
    # only IDENTIFIED names are demanded; Arabic function words (في / من) are never in the demanded
    # set, so a faithful translation full of common English words produces NO missing-name flag.
    _make_reliable(monkeypatch, "ar")
    r = T.name_survival_translit("في محمد من هنا", "Here from Muhammad and everyone today", "ar")
    assert r["verifiable"] is True
    assert r["missing_names"] == []           # zero false flags


# --- integration with survival_checks() -------------------------------------------------------

def test_survival_checks_real_arabic_names_unverifiable():
    # the non-Latin branch of survival_checks must NOT fake a pass: names_verifiable is False and
    # (per the module contract) `ok` is NOT gated on verifiable here — assert on the verifiable bool.
    c = survival_checks("محمد ذهب إلى باريس", "Muhammad went to Paris", "ar", "en")
    assert c["names_verifiable"] is False
    assert c["missing_names"] == []


def test_survival_checks_reliable_path_folds_missing_name(monkeypatch):
    _make_reliable(monkeypatch, "ar")
    good = survival_checks("محمد ذهب إلى العمل", "Muhammad went to work", "ar", "en")
    assert good["names_verifiable"] is True and good["missing_names"] == []
    bad = survival_checks("محمد ذهب", "Ahmed went", "ar", "en")
    assert bad["names_verifiable"] is True and "mHmd" in bad["missing_names"]
    assert bad["ok"] is False                 # a demanded name dropped -> not ok


# --- surface-for-review (Phase 8 task 5), pure/offline -----------------------------------------

def test_build_review_surfaces_specific_reasons():
    from transcript_truth.translate import _build_review
    checks = {"missing_numbers": [17], "introduced_numbers": [], "missing_names": ["Bergstrom"],
              "numbers_verifiable": True, "names_verifiable": False, "ok": False,
              "passed": 0, "total": 2}
    review = _build_review(checks, agree=0.30, have_both=True)
    kinds = {r["check"] for r in review}
    assert {"missing_number", "missing_name", "names_unverifiable", "low_agreement"} <= kinds
    # every surfaced reason carries the four review keys
    for r in review:
        assert {"check", "severity", "evidence", "detail"} <= set(r)


def test_build_review_no_output_is_critical():
    from transcript_truth.translate import _build_review
    review = _build_review(None, 0.0, False)
    assert review and review[0]["check"] == "no_output" and review[0]["severity"] == "critical"
