"""Phase F — second gated coherence voter (MODEL_MAP.md Stage 4). Two gated LLM voters
(Qwen + Gemini) must AGREE on the same in-candidate pick to flag — cutting false positives.
Voters injected as plain callables (prompt->str), so no live model is needed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.coherence import coherence_homophones

# 対象 / 大賞 share a reading (from the reading index).
_TEXT = "対象を選ぶ"


def _voter(pick):
    return lambda prompt: pick


def test_two_voters_agree_flags_with_confidence():
    flags = coherence_homophones(_TEXT, voters=[_voter("大賞"), _voter("大賞")])
    assert any(f.rule == "coherence_homophone" and f.evidence == "対象" for f in flags)
    assert any("both models agree" in f.label for f in flags)


def test_two_voters_disagree_no_flag():
    # one says the written word (no change), the other an alternate -> no majority -> no flag
    flags = coherence_homophones(_TEXT, voters=[_voter("対象"), _voter("大賞")])
    assert flags == []


def test_second_voter_cannot_push_non_candidate():
    # Gemini hallucinates a non-candidate; gate drops it, leaving only Qwen -> no majority of 2
    flags = coherence_homophones(_TEXT, voters=[_voter("気温"), _voter("大賞")])
    assert flags == []


def test_single_voter_still_flags_backcompat():
    flags = coherence_homophones(_TEXT, voters=[_voter("大賞")])
    assert any(f.evidence == "対象" for f in flags)
    assert not any("both models agree" in f.label for f in flags)
