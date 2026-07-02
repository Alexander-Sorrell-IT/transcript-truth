"""Phase A — independent-family voting + on-demand local tier (MODEL_MAP.md Stage 1).

The vote counts INDEPENDENT families, not raw reads, so two same-base Whisper witnesses can't
form a false majority. roster_panel folds in free local witnesses only when the cloud roster
doesn't reach an independent-family majority.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import consensus, chunking
from transcript_truth.consensus import _family, _majority, consensus_vote, roster_panel


# ---------- family rule ----------

def test_same_base_whisper_shares_family():
    assert _family("hf") == _family("whisper")            # same base weights -> 1 vote
    assert _family("hf@0.65x") == _family("whisper")       # slow-rate suffix stripped


def test_specialized_variants_are_independent():
    fams = {_family(n) for n in ("deepgram", "scribe", "gemini", "phowhisper", "wav2vec2", "mms")}
    assert len(fams) == 6                                  # all distinct votes


# ---------- family-aware majority ----------

def test_two_whisper_reads_are_not_a_majority():
    # hf + local whisper agree, but they're the SAME base -> only 1 independent family
    reads = {"hf": "the drug is atorvastatin", "whisper": "the drug is atorvastatin",
             "deepgram": "the drug is a torvastatin"}
    assert _majority(reads) == 1                           # NOT 2 — correlated reads count once


def test_two_independent_families_are_a_majority():
    reads = {"deepgram": "fifty milligrams daily", "gemini": "fifty milligrams daily",
             "hf": "fifteen milligrams daily"}
    assert _majority(reads) == 2
    assert consensus_vote(reads) == "fifty milligrams daily"


def test_vote_falls_to_medoid_without_independent_majority():
    reads = {"hf": "alpha beta gamma", "whisper": "alpha beta gamma", "deepgram": "alpha beta delta"}
    # no 2 independent families agree -> medoid backstop returns a real read (not empty)
    assert consensus_vote(reads) in reads.values()


# ---------- on-demand local tier ----------

def test_local_tier_skipped_when_cloud_agrees(monkeypatch):
    calls = []
    def fake_run(names, audio_path, lang, long, seams):
        calls.append(list(names))
        return {n: "the meeting is at noon" for n in names}     # cloud already agrees
    monkeypatch.setattr(consensus, "_run_witnesses", fake_run)
    monkeypatch.setattr(chunking, "have_ffmpeg", lambda: False)
    reads = roster_panel("x.wav", "en")
    assert len(calls) == 1                                       # local tier never invoked
    assert "whisper" not in reads


def test_local_tier_added_when_cloud_disagrees(monkeypatch):
    calls = []
    def fake_run(names, audio_path, lang, long, seams):
        calls.append(list(names))
        # every witness returns something different -> no independent majority
        return {n: f"read from {n}" for n in names}
    monkeypatch.setattr(consensus, "_run_witnesses", fake_run)
    monkeypatch.setattr(consensus, "_local_available", lambda n: True)
    monkeypatch.setattr(chunking, "have_ffmpeg", lambda: False)
    reads = roster_panel("x.wav", "en")
    assert len(calls) == 2                                       # cloud, then local tier
    assert any(n in reads for n in ("whisper", "mms", "seamless"))
