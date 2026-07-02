"""Phase 2 — coherence witness (JP homophone decider). Uses the real Sudachi tokenizer +
reading index, with the model (qwen) STUBBED. Proves the closed-list gate: the model can
only pick a real same-reading candidate; it cannot invent a non-homophone rewrite.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_truth import coherence
from transcript_truth.coherence import coherence_homophones, reading_index, _kata2hira


def _stub(monkeypatch, reply):
    monkeypatch.setattr(coherence, "qwen", lambda *a, **k: reply)


def test_reading_index_loads():
    assert len(reading_index()) > 0


def test_flags_when_model_picks_valid_alternate(monkeypatch):
    # 対象/大賞 share reading; model picks a different real candidate -> flag
    _stub(monkeypatch, "大賞")
    flags = coherence_homophones("対象を選ぶ")
    assert any(f.rule == "coherence_homophone" and f.evidence == "対象" for f in flags)


def test_no_flag_when_model_confirms_written_word(monkeypatch):
    _stub(monkeypatch, "対象")   # model agrees with what's written
    assert coherence_homophones("対象を選ぶ") == []


def test_non_candidate_reply_is_rejected(monkeypatch):
    # model tries to invent a word NOT in the same-reading candidate list -> gate drops it
    _stub(monkeypatch, "気温")
    assert coherence_homophones("対象を選ぶ") == []


def test_model_exception_swallowed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no model")
    monkeypatch.setattr(coherence, "qwen", boom)
    assert coherence_homophones("対象を選ぶ") == []


def test_kata2hira_converts():
    assert _kata2hira("カ") == "か"
