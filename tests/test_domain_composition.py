"""Lock for the language × field × site composition (Phase 9).

Pins the invariants so they can never silently regress:
  • full CVL == language(en) × field(legal) × site(transcribeme) — flags + grade + fixers ==
    the standalone `legal` profile
  • the SITE axis works: tm_* format lives in `transcribeme`, NOT in the site-neutral `legal` field
  • compose() dedups scanners; every medical scanner composes in
  • coverage map reports field + site; a dropped `{layer}_{lang}_rules.py` auto-wires
These guard the SLOT the whole multi-language / multi-site plan depends on.
"""
from transcript_truth import audit_transcript
from transcript_truth.domains import (compose, coverage_report, language_profiles,
                                      scaffold_domain_layer, DOMAIN_REGISTRY, SITE_REGISTRY)
from transcript_truth.profiles import get as get_profile
import transcript_truth.medical_rules as MR
import inspect

_BATTERY = [
    "THE COURT    We are on the record at 11:19 a.m.\nQ    OK, that's alot to ask, gonna go.",
    "MR. JONES    I'm a U.S. citizen and I would've waited.",
    "A    Uh, Mm-hmm. About 50% health care with Mrs. Carmody.",
    "okay, this is already clean verbatim for legal per the guide.",
    "",
    "SPEAKER 1:    single line",
    "no label just text here that is fine",
    "Numbers: I have 3 cats and twenty dogs.",
]
_HARD = {"moderate", "critical"}
# full TranscribeMe CVL is now the three-axis compose:
_CVL = dict(profile="en", domain="legal", site="transcribeme")


def _hard(flags):
    return sorted((f.line, f.rule, f.severity, f.label) for f in flags if f.severity in _HARD)


def test_full_cvl_hard_flag_parity_with_standalone_legal():
    for text in _BATTERY:
        mono = audit_transcript(text, profile="legal")
        comp = audit_transcript(text, **_CVL)
        assert _hard(mono.flags) == _hard(comp.flags), f"CVL hard-flag parity broke on: {text!r}"
        assert mono.grade == comp.grade, f"grade parity broke on: {text!r}"


def test_full_cvl_scanner_superset_of_standalone():
    mono = {s.__name__ for s in get_profile("legal").scanners}
    comp = {s.__name__ for s in compose("en", "legal", "transcribeme").scanners}
    assert not (mono - comp), f"legal+transcribeme missing standalone-legal scanners: {mono - comp}"


def test_full_cvl_fixer_parity():
    mono = get_profile("legal").fixers
    comp = compose("en", "legal", "transcribeme").fixers
    assert len(comp) == len(mono) and len(mono) > 0, (len(comp), len(mono))


def test_site_axis_separates_tm_format_from_legal_field():
    tm = {"tm_sound_tags", "tm_lowercase_terms", "tm_speaker_caps", "tm_double_dash", "tm_spoken_punct"}
    legal_only = {s.__name__ for s in compose("en", "legal").scanners}
    with_site = {s.__name__ for s in compose("en", "legal", "transcribeme").scanners}
    site_only = {s.__name__ for s in compose("en", None, "transcribeme").scanners}
    assert not (tm & legal_only), "tm_* format leaked into the site-neutral legal field"
    assert tm <= with_site, "legal+transcribeme is missing tm_* format rules"
    assert tm <= site_only, "the transcribeme site is missing its tm_* rules"


def test_compose_dedups_scanners():
    names = [s.__name__ for s in compose("en", "legal", "transcribeme").scanners]
    assert len(names) == len(set(names)), "compose() left duplicate scanners"


def test_all_medical_scanners_wired():
    med_defs = {n for n, o in inspect.getmembers(MR, inspect.isfunction)
                if o.__module__ == MR.__name__ and not n.startswith("_")}
    composed = {s.__name__ for s in compose("en", "medical").scanners}
    assert med_defs <= composed, f"unwired medical scanners: {med_defs - composed}"


def test_coverage_report_covers_field_and_site():
    rows = {(r["language"], r["layer"]): r for r in coverage_report()}
    assert rows[("en", "legal")]["coverage"] == "full" and rows[("en", "legal")]["kind"] == "field"
    assert rows[("en", "medical")]["coverage"] == "full"
    assert rows[("en", "transcribeme")]["coverage"] == "full" and rows[("en", "transcribeme")]["kind"] == "site"
    others = [l for l in language_profiles() if l != "en"]
    assert others and rows[(others[0], "legal")]["coverage"] == "core"


def test_scaffolder_snippet_without_writing():
    r = scaffold_domain_layer("es", "legal", write=False)
    assert not r["created"]
    assert "ES_LEGAL_SCANNERS" in r["register_snippet"]


def test_autodiscover_self_installs_a_dropped_layer():
    """Dropping a `{layer}_{lang}_rules.py` file must auto-wire it — no editing domains.py."""
    import os
    from transcript_truth.domains import autodiscover_domain_layers
    r = scaffold_domain_layer("zz", "legal", write=True)
    try:
        found = autodiscover_domain_layers()
        assert ("legal", "zz") in found
        assert "zz" in DOMAIN_REGISTRY["legal"]["per_language"]
    finally:
        DOMAIN_REGISTRY["legal"]["per_language"].pop("zz", None)
        if os.path.exists(r["path"]):
            os.remove(r["path"])
