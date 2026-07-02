"""Phase 3 — the engine heart: consensus.py deterministic functions (no audio, no models).

Covers the crown jewels:
  _splice        — the seam-stitch SAFETY INVARIANT: never lose A's words.
  consensus      — roster-agnostic voting (the fix for the 'silently single-model' bug):
                   works over WHATEVER two witnesses survived, not hardcoded names.
  consensus_vote / _majority — majority + medoid tiebreak.
  completeness   — catch dropped content the auditor is blind to.
  _merge_diarized_chunks — per-chunk speaker-id reconciliation at seams.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_truth.consensus import (
    _splice, _norm_ws, consensus_vote, _majority, consensus, completeness,
    _merge_diarized_chunks,
)


# ---------- _splice: safety invariant ----------

def test_splice_trims_duplicated_overlap():
    # overlap must be >= min_anchor (4 words): "sat on the mat"
    out, ok = _splice("the cat sat on the mat", "sat on the mat and slept")
    assert ok is True
    assert out == "the cat sat on the mat and slept"   # 4-word overlap not doubled


def test_splice_never_loses_A_when_no_overlap():
    # no clean seam -> keep ALL of A and ALL of B, flag seam as not-clean
    a, b = "alpha beta gamma delta", "totally unrelated words here"
    out, ok = _splice(a, b)
    assert ok is False
    for w in a.split():
        assert w in out           # A is never cut — the core invariant


def test_splice_empty_sides():
    assert _splice("", "hello world") == ("hello world", True)
    assert _splice("hello world", "") == ("hello world", True)


# ---------- _norm_ws ----------

def test_norm_ws_strips_punct_and_case():
    assert _norm_ws("Hello, WORLD!") == "hello world"


# ---------- consensus_vote / _majority ----------

def test_majority_counts_agreement():
    assert _majority({"a": "the same text", "b": "the same text", "c": "different"}) == 2
    assert _majority({}) == 0


def test_consensus_vote_returns_majority_read():
    reads = {"m1": "the quick brown fox", "m2": "the quick brown fox", "m3": "a wholly other line"}
    assert consensus_vote(reads) == "the quick brown fox"


def test_consensus_vote_empty():
    assert consensus_vote({"a": "", "b": ""}) == ""


# ---------- consensus: roster-agnostic ----------

def test_consensus_is_roster_agnostic():
    # arbitrary witness names (NOT hardcoded scribe/whisper) must still work
    reads = {"deepgram": "the meeting starts at noon today",
             "gemini": "the meeting starts at noon today",
             "some_new_model": "the meeting starts at noon friday"}
    r = consensus(reads)
    assert r["n_models"] == 3
    assert r["base_model"] in reads            # a real base was chosen
    assert r["agreement_pct"] > 0


def test_consensus_single_model_degrades_gracefully():
    r = consensus({"only": "just one read"})
    assert r["n_models"] == 1 and r["base"] == "just one read"


# ---------- completeness ----------

def test_completeness_full_when_content_survives():
    base = "契約書 の 内容 を 確認 する"
    assert completeness(base, base) == 1.0


def test_completeness_drops_when_content_missing():
    base = "契約書 の 内容 を 確認 する 会議 記録"
    final = "契約書"                       # most content words dropped
    assert completeness(base, final) < 0.7


# ---------- _merge_diarized_chunks ----------

def test_merge_empty_returns_empty():
    assert _merge_diarized_chunks([], overlap_s=5) == []


def test_merge_single_chunk_passthrough():
    turns = [{"start": 0.0, "end": 2.0, "speaker": "speaker_0", "text": "hi"}]
    out = _merge_diarized_chunks([(0.0, turns)], overlap_s=5)
    assert len(out) == 1 and out[0]["text"] == "hi"
