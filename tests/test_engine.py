"""Phase 4 — engine.py: parse_transcript + audit_transcript, including the opt-in
coherence=True witness path (JP + EN homophone routing), with models stubbed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import engine
from transcript_truth.engine import parse_transcript, audit_transcript


def test_parse_transcript_numbers_lines():
    t = parse_transcript("line one\nline two")
    assert [l.n for l in t.lines] == [1, 2]
    assert t.lines[0].text == "line one"


def test_audit_clean_default_profile():
    r = audit_transcript("Speaker 1: This is clean.")
    assert r.grade == "A" and r.flags == []


def test_audit_composes_domain_and_site():
    # legal + transcribeme site path (compose branch)
    r = audit_transcript("He [laughs] said see Page 5.", profile="en", domain="legal", site="transcribeme")
    assert any(f.rule.startswith("tm_") for f in r.flags)


def test_coherence_path_routes_and_flags(monkeypatch):
    # stub both witnesses; JP run -> coherence_homophones, EN run -> en_homophone_errors
    import transcript_truth.coherence as coh
    import transcript_truth.en_rules as enr
    monkeypatch.setattr(coh, "qwen", lambda *a, **k: "大賞")           # JP picks alternate
    monkeypatch.setattr(enr, "qwen", lambda *a, **k: "there -> their")  # EN homophone
    r = audit_transcript("対象を選ぶ there house", coherence=True, profile="default")
    rules = {f.rule for f in r.flags}
    assert "coherence_homophone" in rules or "en_homophone" in rules
    # review-tier flags cap the grade below A but don't crater it
    assert r.grade in ("B", "C")


def test_coherence_off_by_default_stays_model_free(monkeypatch):
    # if coherence defaulted on, a boom-stub would blow up; it must never be called
    import transcript_truth.coherence as coh
    monkeypatch.setattr(coh, "qwen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    r = audit_transcript("対象を選ぶ")
    assert r.grade == "A"
