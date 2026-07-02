"""English homophone scanner (en_rules) — the deterministic CATALOG GATE.

The scanner asks a model (qwen) for homophone corrections, but a flag is accepted ONLY if
both words live in the same confusable set (data/en_homophones.json). That gate is the safety
claim: the model can't push a non-homophone rewrite through. We test the pure gate directly,
and the full scanner with the model STUBBED (no live key needed) to prove the gate holds.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_truth import en_rules
from transcript_truth.en_rules import _norm, _same_set, _index, en_homophone_errors


# ---------- pure gate ----------

def test_norm_strips_apostrophes_and_punct():
    assert _norm("They're") == "theyre"
    assert _norm("it's.") == "its"


def test_catalog_loads_nonempty():
    assert len(_index()) > 0


def test_same_set_accepts_real_homophones():
    assert _same_set("there", "their")
    assert _same_set("your", "you're")   # apostrophe-insensitive


def test_same_set_rejects_non_homophones():
    assert not _same_set("there", "dog")
    assert not _same_set("cat", "hat")   # neither in catalog


# ---------- full scanner with model stubbed ----------

def _stub_qwen(monkeypatch, reply):
    monkeypatch.setattr(en_rules, "qwen", lambda *a, **k: reply)


def test_empty_when_no_letters(monkeypatch):
    _stub_qwen(monkeypatch, "should not be called")
    assert en_homophone_errors("12345 !!!") == []


def test_valid_homophone_pair_flagged(monkeypatch):
    _stub_qwen(monkeypatch, "there -> their")
    flags = en_homophone_errors("I lost there house.")
    assert len(flags) == 1
    assert flags[0].rule == "en_homophone" and flags[0].evidence == "there"


def test_non_homophone_rewrite_rejected(monkeypatch):
    # model tries to push a NON-homophone correction — gate must drop it
    _stub_qwen(monkeypatch, "house -> home")
    assert en_homophone_errors("I lost there house.") == []


def test_suggestion_for_word_not_in_text_rejected(monkeypatch):
    # 'their -> there' but 'their' isn't in the text -> no anchor, dropped
    _stub_qwen(monkeypatch, "their -> there")
    assert en_homophone_errors("The dog ran fast.") == []


def test_model_none_reply_yields_no_flags(monkeypatch):
    _stub_qwen(monkeypatch, "none")
    assert en_homophone_errors("A perfectly clean sentence.") == []


def test_model_exception_is_swallowed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no api key")
    monkeypatch.setattr(en_rules, "qwen", boom)
    assert en_homophone_errors("I lost there house.") == []
