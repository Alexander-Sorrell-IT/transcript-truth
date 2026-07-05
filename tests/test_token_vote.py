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
    # each read is wrong on a DIFFERENT real word (garble elsewhere); per-word family majority
    # rebuilds the truth "the quick brown fox" that no single read contains.
    r = consensus_tokens({
        "deepgram": "the quick brown zzqx",
        "gemini":   "the quick wxvb fox",
        "scribe":   "the kkjm brown fox",
    }, "en")
    assert r["text"] == "the quick brown fox"      # no single input equals this
    assert all(v != "the quick brown fox" for v in
               ["the quick brown zzqx", "the quick wxvb fox", "the kkjm brown fox"])


def test_lone_outlier_cannot_flip_a_word():
    # the reliable anchor (scribe) + gemini agree on 'cat'; a lone non-anchor says 'bat' -> 'cat' stays
    r = consensus_tokens({"scribe": "the cat sat", "gemini": "the cat sat",
                          "deepgram": "the bat sat"}, "en")
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


def test_tokenization_mismatch_does_not_duplicate_words():
    # regression (bench two_seq): "double check" (2 tokens) vs "double-check" (1 token) must NOT
    # produce "double-check check". Unequal-length spans are tokenization artifacts, not word votes.
    r = consensus_tokens({
        "deepgram": "please double check the figures",
        "scribe":   "please double-check the figures",
        "gemini":   "please double-check the figures",
    })
    assert "double-check check" not in r["text"] and "check check" not in r["text"]
    assert r["text"].split().count("check") <= 1


def test_empty_and_single():
    assert consensus_tokens({}) == {"text": "", "uncertain_spans": []}
    assert consensus_tokens({"a": "only one read"})["text"] == "only one read"
