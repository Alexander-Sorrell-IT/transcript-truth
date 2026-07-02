"""Phase C — explicit two-tier slow path (MODEL_MAP.md Stage 2).

Tier 1 normal always; Tier 2 slow escalates on uncertainty for general content, but ALWAYS runs
for legal/medical. All audio I/O stubbed (roster_panel, _stretch, os.remove).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import consensus
from transcript_truth.consensus import transcribe

_AGREE = {"deepgram": "the meeting is at noon", "gemini": "the meeting is at noon"}   # 2 families
_DISAGREE = {"deepgram": "the meeting is at noon", "gemini": "the meeting is at two"}  # split


def _wire(monkeypatch, normal_reads, slow_reads=None):
    calls = {"n": 0}
    def fake_roster(path, lang, seams=None):
        calls["n"] += 1
        return dict(slow_reads) if (slow_reads and calls["n"] > 1) else dict(normal_reads)
    monkeypatch.setattr(consensus, "roster_panel", fake_roster)
    monkeypatch.setattr(consensus, "_stretch", lambda a, r: "slow.wav")
    monkeypatch.setattr(consensus.os, "remove", lambda p: None)
    return calls


def test_general_confident_skips_slow(monkeypatch):
    calls = _wire(monkeypatch, _AGREE)
    r = transcribe("x.wav", "en")
    assert r["slowed"] == [] and calls["n"] == 1          # normal only
    assert r["slow_changed"] is False


def test_general_uncertain_escalates_to_slow(monkeypatch):
    # normal disagrees; slow converges -> stops after first rate
    calls = _wire(monkeypatch, _DISAGREE, slow_reads=_AGREE)
    r = transcribe("x.wav", "en")
    assert r["slowed"] == [0.65]                          # escalated, converged, stopped
    assert calls["n"] == 2


def test_legal_always_runs_full_slow_ladder(monkeypatch):
    # normal is ALREADY confident, but legal double-checks anyway across BOTH rates
    calls = _wire(monkeypatch, _AGREE)
    r = transcribe("x.wav", "en", domain="legal")
    assert r["slowed"] == [0.65, 0.5]                     # full ladder, no early stop
    assert r["domain"] == "legal"


def test_medical_also_always_slows(monkeypatch):
    _wire(monkeypatch, _AGREE)
    r = transcribe("x.wav", "en", domain="medical")
    assert r["slowed"] == [0.65, 0.5]


def test_normal_text_preserved_and_compare_flag(monkeypatch):
    _wire(monkeypatch, _DISAGREE, slow_reads=_AGREE)
    r = transcribe("x.wav", "en")
    assert r["normal_text"] in ("the meeting is at noon", "the meeting is at two")
    # slow folded in a converging read; the compare flag exists as a bool
    assert isinstance(r["slow_changed"], bool)
