"""Pure-function core: metrics (WER + diarization ruler), grade_and_verdict, language detect.

These are the deterministic measurement/verdict primitives the whole engine rests on
(the 95.8% diarization decision was made with diar_agreement; the grade path has no LLM).
Deterministic = testable — same discipline as the rest of the suite.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_truth.metrics import wer, diar_agreement, _normalize_numbers
from transcript_truth.grade import grade_and_verdict
from transcript_truth.types import Flag
from transcript_truth import language


# ---------- WER ----------

def test_wer_identical_is_zero():
    assert wer("the quick brown fox", "the quick brown fox") == 0.0


def test_wer_case_and_punct_insensitive():
    assert wer("Hello, world!", "hello world") == 0.0


def test_wer_one_substitution():
    # 1 error over 4 reference words
    assert wer("the quick brown fox", "the quick brown dog") == 0.25


def test_wer_deletion_counts():
    assert wer("a b c d", "a b c") == 0.25


def test_wer_empty_reference():
    assert wer("", "") == 0.0
    assert wer("", "anything here") == 1.0


def test_wer_number_normalization_default_on():
    # "15%" vs "fifteen percent" should NOT be an error under number normalization
    assert wer("it rose 15%", "it rose fifteen percent") == 0.0


def test_wer_number_normalization_can_be_disabled():
    assert wer("it rose 15%", "it rose fifteen percent", normalize_numbers=False) > 0.0


def test_wer_cjk_tokenized_by_character():
    # space-free scripts have no word boundaries; WER must tokenize CJK by char, not by space
    assert wer("三月三日", "三月三日") == 0.0
    assert wer("三月三日", "三月四日") == 0.25          # 1 of 4 chars wrong (not 1.0)
    assert wer("응우옌 박사가", "응우옌 사사가") == round(1 / 6, 4)  # 6 Hangul chars, 1 wrong


def test_normalize_numbers_scale_merge():
    # "47 million" and "forty seven million" canonicalize to the same integer
    assert _normalize_numbers("47 million") == _normalize_numbers("forty seven million")


# ---------- diar_agreement ----------

def _turns(*spans):
    return [{"start": s, "end": e, "speaker": spk} for s, e, spk in spans]


def test_diar_perfect_agreement():
    ref = _turns((0, 5, "A"), (5, 10, "B"))
    hyp = _turns((0, 5, "spk0"), (5, 10, "spk1"))  # different ids, same timeline
    r = diar_agreement(ref, hyp)
    assert r["agreement_pct"] == 100.0
    assert r["ref_speakers"] == 2 and r["hyp_speakers"] == 2


def test_diar_id_labels_dont_matter():
    # ids swapped relative to ref, but overlap-voting should remap them
    ref = _turns((0, 5, "A"), (5, 10, "B"))
    hyp = _turns((0, 5, "B"), (5, 10, "A"))
    assert diar_agreement(ref, hyp)["agreement_pct"] == 100.0


def test_diar_disagreement_scores_low():
    # ref has two speakers; hyp misattributes the back half to the wrong one
    ref = _turns((0, 5, "A"), (5, 10, "B"))
    hyp = _turns((0, 5, "A"), (5, 10, "A"))  # second half assigned to A, should be B
    r = diar_agreement(ref, hyp)
    assert r["agreement_pct"] < 100.0


def test_diar_reports_phantom_speaker_count():
    # single true speaker, hyp invents a second — remaps to 100% but count diverges
    ref = _turns((0, 10, "A"))
    hyp = _turns((0, 5, "A"), (5, 10, "B"))
    r = diar_agreement(ref, hyp)
    assert r["hyp_speakers"] == 2 and r["ref_speakers"] == 1


def test_diar_empty_inputs():
    assert diar_agreement([], [])["agreement_pct"] == 0


# ---------- grade_and_verdict ----------

def _flag(sev):
    return Flag(rule="x", label="l", severity=sev)


def test_grade_clean_is_A():
    grade, score, n_crit, _ = grade_and_verdict([])
    assert grade == "A" and score == 0 and n_crit == 0


def test_grade_two_criticals_is_F():
    grade, _, n_crit, _ = grade_and_verdict([_flag("critical"), _flag("critical")])
    assert grade == "F" and n_crit == 2


def test_grade_one_critical_is_D():
    assert grade_and_verdict([_flag("critical")])[0] == "D"


def test_grade_one_moderate_is_B():
    assert grade_and_verdict([_flag("moderate")])[0] == "B"


def test_grade_two_moderates_is_C():
    assert grade_and_verdict([_flag("moderate"), _flag("moderate")])[0] == "C"


def test_grade_open_review_caps_below_A():
    # a "review" item carries no score weight but blocks a clean A
    assert grade_and_verdict([_flag("review")])[0] == "B"


def test_grade_minor_does_not_move_grade():
    assert grade_and_verdict([_flag("minor")])[0] == "A"


# ---------- language detection (script/lang classification) ----------

def test_script_of_basic():
    assert language.script_of("a") == "en"
    assert language.script_of("あ") == "ja"
    assert language.script_of("한") == "ko"
    assert language.script_of("д") == "cyr"


def test_lang_of_english_and_japanese():
    assert language.lang_of("hello there") == "en"
    assert language.lang_of("こんにちは") == "ja"


def test_segments_splits_at_script_boundary():
    segs = language.segments("hello こんにちは")
    langs = [l for l, _ in segs]
    assert "en" in langs and "ja" in langs
