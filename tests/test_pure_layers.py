"""Phase 1 — pure deterministic layers with no model/IO dependency:
finish (clean-verbatim finishing), report (HTML), decision (collocation resolver),
disambiguate (homophone decider with an injected LLM).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_truth.finish import clean_verbatim_finish
from transcript_truth.report import to_html
from transcript_truth import decision as decision_mod
from transcript_truth.decision import make_decision
from transcript_truth.disambiguate import find_trap, disambiguate
from transcript_truth.types import Flag, Receipt, Transcript, Line
from transcript_truth.semantic import ENTRIES


# ---------- finish.py ----------

def test_finish_removes_standalone_filler():
    assert "えーと" not in clean_verbatim_finish("えーと、これは test です")


def test_finish_keeps_meaningful_demonstrative():
    # あの人 = "that person" — must NOT be stripped (not comma-set-off, not before English)
    assert "あの人" in clean_verbatim_finish("あの人が来た")


def test_finish_fixes_mixed_script_punctuation():
    out = clean_verbatim_finish("I said hello。")
    assert "hello. " in out and "。" not in out


def test_finish_collapses_double_spaces():
    assert "  " not in clean_verbatim_finish("a   b")


# ---------- report.py ----------

def test_report_clean_receipt_renders_check():
    r = Receipt(grade="A", score=0, n_critical=0, n_lines=1, mode="clean_verbatim", flags=[])
    html = to_html(r)
    assert "Clean against the deterministic rule-set" in html and ">A<" in html


def test_report_flag_rendered_and_escaped():
    f = Flag(rule="x", label="bad <thing>", line=3, severity="critical", evidence="<ev>", fix="do y")
    r = Receipt(grade="F", score=3, n_critical=1, n_lines=1, mode="clean_verbatim", flags=[f])
    html = to_html(r)
    assert "bad &lt;thing&gt;" in html          # HTML-escaped, no injection
    assert "&lt;ev&gt;" in html and "do y" in html
    assert "L3" in html and "critical" in html


# ---------- decision.py (stubbed data for a deterministic scoring test) ----------

def test_decision_resolves_confusable_by_collocation(monkeypatch):
    # trap set {their, there}; 'their' collocates with 'house', 'there' with 'over'
    monkeypatch.setattr(decision_mod, "_sets", lambda lang: {"their": ["their", "there"],
                                                             "there": ["their", "there"]})
    monkeypatch.setattr(decision_mod, "_colloc", lambda lang: {"their": ["house", "car"],
                                                               "there": ["over", "here"]})
    dec = make_decision("en")
    t = Transcript(lines=[Line(n=1, text="I went to there house")])  # 'there' wrong, ctx=house
    flags = dec(t)
    assert any(f.evidence == "there" and "their" in f.label for f in flags)


def test_decision_stays_silent_when_context_matches(monkeypatch):
    monkeypatch.setattr(decision_mod, "_sets", lambda lang: {"their": ["their", "there"],
                                                             "there": ["their", "there"]})
    monkeypatch.setattr(decision_mod, "_colloc", lambda lang: {"their": ["house"],
                                                               "there": ["over"]})
    dec = make_decision("en")
    t = Transcript(lines=[Line(n=1, text="their house is big")])   # correct already
    assert dec(t) == []


# ---------- disambiguate.py (injected LLM) ----------

def test_find_trap_locates_known_homophone():
    entry = ENTRIES[0]
    kanji = entry["members"][0][0]
    e, used = find_trap(f"これは{kanji}です")
    assert e is not None and used == kanji


def test_disambiguate_returns_none_when_no_trap():
    assert disambiguate("just plain english, no kanji", lambda p: {}) is None


def test_disambiguate_flags_error_when_pick_differs():
    entry = ENTRIES[0]
    used, other = entry["members"][0][0], entry["members"][1][0]
    d = disambiguate(f"文の{used}について", lambda p: {"pick": other, "english": "X", "confidence": "high"})
    assert d.is_error is True and d.pick == other and d.used == used


def test_disambiguate_no_error_when_pick_matches():
    entry = ENTRIES[0]
    used = entry["members"][0][0]
    d = disambiguate(f"文の{used}について", lambda p: {"pick": used})
    assert d.is_error is False
