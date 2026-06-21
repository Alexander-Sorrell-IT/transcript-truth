"""The measurement loop. You can't improve what you don't measure.

Injects KNOWN errors into lines, runs the full scanner stack, and reports:
  - recall  (did we catch the planted error?)
  - false positives (did we flag a clean line?)
  - the MEASURED RESIDUAL: error classes with no checker yet = the next builds.

This is the engine of "getting better": measure -> build the dict/checker -> re-measure.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.engine import parse_transcript
from transcript_truth.scanners import run_scanners
from transcript_truth.semantic import homophone_traps


def all_flags(text, mode="clean_verbatim"):
    t = parse_transcript(text, mode)
    return run_scanners(t) + homophone_traps(t)


# (label, text, expected_rule | None for a clean line we must NOT flag)
CASES = [
    ("bad timestamp",        "Speaker 1: it ran from (1:02:30) on.",          "timestamps"),
    ("misplaced ?",          "Speaker? 2: go ahead.",                          "speaker_labels"),
    ("misspelled inaudible", "Speaker 1: then [inaudable 00:01:15] hit.",      "inaudible"),
    ("CV filler",            "Speaker 1: um, you know, it works.",             "fillers"),
    ("homophone 偏在",        "Interviewer: 偏在していたものが減った。",          "homophone_trap"),
    ("homophone 清算/犯",     "Interviewee: 罪を犯した彼が清算をする。",          "homophone_trap"),
    ("CLEAN english",        "Speaker 1: we settle it against the rubric.",    None),
    ("CLEAN ts + ?",         "?Speaker 2: starts at [00:04:12] sharp.",        None),
    ("CLEAN japanese",       "Interviewer: これは普通の文章です。",              None),
]

# Error classes we do NOT yet have a checker for — the honest, MEASURED gap.
UNCOVERED = [
    ("mishearing (ASR word error)", "multi-engine ASR (Whisper+others) cross-check + domain lexicon + in-context plausibility scoring"),
    ("unnatural phrasing",          "collocation / n-gram DB + LM perplexity flag on low-probability spans"),
    ("wrong particle / grammar",    "grammar checker + LM scoring of the surface form"),
]

hit = tot = fp = 0
print(f"  {'case':22}{'expected':16}{'fired':22}result")
print("  " + "-" * 64)
for label, text, exp in CASES:
    rules = sorted({f.rule for f in all_flags(text)})
    fired = ",".join(rules) or "-"
    if exp is None:
        ok = not rules
        fp += 0 if ok else 1
        print(f"  {label:22}{'(clean)':16}{fired:22}{'ok' if ok else 'FALSE POSITIVE'}")
    else:
        tot += 1
        ok = exp in rules
        hit += ok
        print(f"  {label:22}{exp:16}{fired:22}{'CAUGHT' if ok else 'MISSED'}")

print("  " + "-" * 64)
print(f"  recall on injected errors : {hit}/{tot}")
print(f"  false positives on clean  : {fp}")
print(f"\n  MEASURED RESIDUAL — no checker yet (next builds, in priority order):")
for cls, how in UNCOVERED:
    print(f"   • {cls:30} -> {how}")
