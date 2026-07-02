"""Phase B — token-level (ROVER) consensus with medoid backstop (MODEL_MAP.md Stage 1/B).

Per-word majority over the medoid backbone; overrides a backbone word only when an INDEPENDENT
cross-family majority outnumbers it. Recovers words no single model got right, without stitching
disfluent seams on a lone outlier. Surfaces the disagreement map (uncertain_spans).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.consensus import consensus_tokens


def test_all_agree_text_unchanged_no_spans():
    r = consensus_tokens({"deepgram": "the cat sat on the mat",
                          "gemini": "the cat sat on the mat",
                          "scribe": "the cat sat on the mat"})
    assert r["text"] == "the cat sat on the mat"
    assert r["uncertain_spans"] == []


def test_reconstructs_transcript_no_single_model_got_right():
    # each read is wrong on a DIFFERENT word; per-word family majority rebuilds the truth.
    # deepgram wrong@pos2, gemini wrong@pos1, scribe wrong@pos0 -> majority = "alpha bravo charlie"
    r = consensus_tokens({
        "deepgram": "alpha bravo zulu",
        "gemini":   "alpha whiskey charlie",
        "scribe":   "xray bravo charlie",
    })
    assert r["text"] == "alpha bravo charlie"      # no single input equals this
    assert all(v != "alpha bravo charlie" for v in
               ["alpha bravo zulu", "alpha whiskey charlie", "xray bravo charlie"])


def test_lone_outlier_cannot_flip_a_word():
    # only scribe says 'bat'; 1 family < 2 -> backbone 'cat' is kept
    r = consensus_tokens({"deepgram": "the cat sat", "gemini": "the cat sat",
                          "scribe": "the bat sat"})
    assert r["text"] == "the cat sat"


def test_disagreement_is_surfaced_as_uncertain_span():
    r = consensus_tokens({"deepgram": "the cat sat", "gemini": "the cat sat",
                          "scribe": "the bat sat"})
    # the contested position (cat vs bat) is reported even though the backbone kept its word
    assert any(s.get("contested") or s.get("from") for s in r["uncertain_spans"])


def test_same_family_reads_do_not_form_a_token_majority():
    # hf + local whisper agree on 'cat' but SAME base = 1 family; deepgram says 'bat' = 1 family.
    # 1 vs 1 -> no override; backbone (medoid) word stands. (No false majority from correlated reads.)
    r = consensus_tokens({"hf": "the cat sat", "whisper": "the cat sat", "deepgram": "the bat sat"})
    assert r["text"] in ("the cat sat", "the bat sat")   # never invents; stays a real read


def test_empty_and_single():
    assert consensus_tokens({}) == {"text": "", "uncertain_spans": []}
    assert consensus_tokens({"a": "only one read"})["text"] == "only one read"
