"""Phase E — diarization cost guard (MODEL_MAP.md Stage 3): single primary diarizer when
confident; cross-vote (diarize_consensus) only when the primary looks unsure. Diarizers stubbed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import consensus
from transcript_truth.consensus import diarize_best


def _turns(n_speakers):
    return [{"start": float(i), "end": float(i) + 1, "speaker": f"s{i % n_speakers}", "text": "x"}
            for i in range(n_speakers)]


def test_confident_primary_used_no_crossvote(monkeypatch):
    called = {"consensus": 0}
    monkeypatch.setattr(consensus, "diarize_long", lambda a, l, d: _turns(3))
    monkeypatch.setattr(consensus, "diarize_consensus",
                        lambda a, l: called.__setitem__("consensus", called["consensus"] + 1) or {})
    r = diarize_best("x.wav", "en")
    assert r["method"] == "deepgram" and r["speakers"] == 3
    assert called["consensus"] == 0                      # never escalated


def test_empty_primary_escalates_to_crossvote(monkeypatch):
    monkeypatch.setattr(consensus, "diarize_long", lambda a, l, d: [])
    monkeypatch.setattr(consensus, "diarize_consensus",
                        lambda a, l: {"turns": _turns(2), "agreement_pct": 88.0})
    r = diarize_best("x.wav", "en")
    assert r["method"] == "consensus" and r["speakers"] == 2 and r["agreement_pct"] == 88.0


def test_implausible_speaker_count_escalates(monkeypatch):
    monkeypatch.setattr(consensus, "diarize_long", lambda a, l, d: _turns(20))   # over-segmented
    monkeypatch.setattr(consensus, "diarize_consensus",
                        lambda a, l: {"turns": _turns(3), "agreement_pct": 95.0})
    r = diarize_best("x.wav", "en", max_speakers=8)
    assert r["method"] == "consensus" and r["speakers"] == 3


def test_primary_exception_escalates(monkeypatch):
    def boom(a, l, d): raise RuntimeError("diarizer down")
    monkeypatch.setattr(consensus, "diarize_long", boom)
    monkeypatch.setattr(consensus, "diarize_consensus",
                        lambda a, l: {"turns": _turns(2), "agreement_pct": 90.0})
    assert diarize_best("x.wav", "en")["method"] == "consensus"
