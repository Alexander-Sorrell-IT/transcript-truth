"""Deterministic = testable. Same discipline as RoboTruth's 81 engine tests."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import audit_transcript


def test_clean_passes():
    r = audit_transcript("Speaker 1: This is a clean line.\nSpeaker 2: And so is this one.")
    assert r.grade == "A" and r.flags == []


def test_misplaced_uncertain_speaker_flagged():
    r = audit_transcript("Speaker? 1: hello there.")
    assert any(f.rule == "speaker_labels" for f in r.flags)


def test_correct_uncertain_speaker_is_clean():
    r = audit_transcript("?Speaker 1: hello there.")
    assert all(f.rule != "speaker_labels" for f in r.flags)


def test_bad_timestamp_flagged():
    r = audit_transcript("Speaker 1: it was (1:02:30) ish.")
    assert any(f.rule == "timestamps" for f in r.flags)


def test_good_timestamp_is_clean():
    r = audit_transcript("Speaker 1: it was [01:02:30] ish.")
    assert all(f.rule != "timestamps" for f in r.flags)


def test_inaudible_misspelling_flagged():
    r = audit_transcript("Speaker 1: then [inaudable 00:01:15] happened.")
    assert any(f.rule == "inaudible" for f in r.flags)


def test_good_inaudible_is_clean():
    r = audit_transcript("Speaker 1: then [inaudible 00:01:15] happened.")
    assert all(f.rule != "inaudible" for f in r.flags)


def test_fillers_only_in_clean_verbatim():
    text = "Speaker 1: um, you know, it works."
    assert any(f.rule == "fillers" for f in audit_transcript(text, "clean_verbatim").flags)
    assert all(f.rule != "fillers" for f in audit_transcript(text, "full_verbatim").flags)


def test_grade_is_pure_function():
    text = "Speaker 1: it was (1:02:30) ish."
    assert audit_transcript(text).grade == audit_transcript(text).grade  # deterministic


# --- regression: adversarial-audit findings (2026-06-19) ---

def test_kana_spelling_variant_is_not_an_error():
    """珈琲/コーヒー, 顎/あご etc. are the SAME word spelled two ways -> must not flag."""
    from transcript_truth.verdict import verify
    for k, e in [("珈琲", "コーヒー"), ("煙草", "タバコ"), ("有難う", "ありがとう"), ("顎", "あご")]:
        assert verify(k, e) == [], f"false positive on spelling variant {k}/{e}"


def test_genuine_homophone_still_flagged():
    from transcript_truth.verdict import verify
    assert verify("記者", "汽車"), "different-meaning homophone must still surface"
    assert verify("群島", "軍島")[0]["verdict"] == "LIKELY_MISHEARD"  # non-word caught


def test_jp_filler_does_not_fire_inside_real_words():
    """へえー / なんかい(何回) / まあまあ must NOT trigger filler flags."""
    for txt in ["へえー、そうですか。", "なんかいもありました。", "まあまあ、落ち着いて。"]:
        assert all(f.rule != "fillers" for f in audit_transcript(txt).flags), txt
    # but a standalone hesitation filler STILL fires
    assert any(f.rule == "fillers" for f in audit_transcript("。えーと、そうですね。").flags)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
