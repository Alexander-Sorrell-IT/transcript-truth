"""Pitch-accent witness tests. Pure dictionary lookup (no model, no audio) — it
splits same-reading homophones into pitch-distinguishable vs truly-identical."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.pitch_accent import accents, distinguish, hint
from transcript_truth.verdict import verify


def test_accents_lookup():
    assert 1 in accents("箸", "はし")     # atamadaka
    assert 2 in accents("橋", "はし")     # odaka

def test_distinguishable_pairs():
    assert distinguish("橋", "箸", "はし")["distinguishable"]    # 2 vs 1
    assert distinguish("雨", "飴", "あめ")["distinguishable"]    # 1 vs 0
    assert distinguish("神", "紙", "かみ")["distinguishable"]    # 1 vs 2

def test_truly_identical_not_distinguishable():
    # the irreducible core — same accent, audio genuinely can't decide
    assert not distinguish("華氏", "菓子", "かし")["distinguishable"]    # both 1
    assert not distinguish("動悸", "動機", "どうき")["distinguishable"]  # both 0

def test_hint_text():
    h = hint("橋", "箸", "はし")
    assert h and "橋" in h and "箸" in h and "accent" in h
    assert hint("華氏", "菓子", "かし") is None   # not distinguishable -> no hint

def test_verify_marks_pitch_resolvable():
    # 雨/飴 differ in accent -> verdict should be PITCH_RESOLVABLE, not bare AMBIGUOUS
    flags = verify("雨が好きです。", "飴が好きです。")
    verdicts = {f["verdict"] for f in flags}
    assert "PITCH_RESOLVABLE" in verdicts, verdicts

def test_verify_keeps_ambiguous_when_pitch_identical():
    # 華氏/菓子 same accent -> stays AMBIGUOUS (honest: context-only)
    flags = verify("華氏で測る。", "菓子で測る。")
    verdicts = {f["verdict"] for f in flags}
    assert "PITCH_RESOLVABLE" not in verdicts, verdicts


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
