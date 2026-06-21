"""RoboTruth-on-top: Qwen (worker) corrects the Japanese; our DETERMINISTIC engine
audits its output -- no model gets the final word.

  raw draft --[Qwen worker]--> corrected --[deterministic auditor]--> receipt
  Every change Qwen makes is checked: is the new word real (dictionary)? + English gloss.
  Qwen's final text is run through our scanners: anything it still got wrong surfaces.
"""
import sys, os, difflib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.worker import correct_transcript
from transcript_truth.engine import audit_transcript
from transcript_truth.verdict import gloss, _toks, name_index

RAW = sys.argv[1] if len(sys.argv) > 1 else "わっ。ビックリした。動機がすごいよ。以外にビビりだね。"

print("RAW   (worker input) :", RAW)
corrected = correct_transcript(RAW)
print("QWEN  (worker output):", corrected)
print("=" * 64)

# what did Qwen change?
rt = [m.surface() for m in _toks(RAW)]
ct = [m.surface() for m in _toks(corrected)]
print("AUDIT of each change Qwen made (deterministic, no model):")
any_change = False
for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=rt, b=ct, autojunk=False).get_opcodes():
    if op == "equal":
        continue
    old, new = "".join(rt[i1:i2]), "".join(ct[j1:j2])
    if not new.strip("。、！？「」 　"):
        continue
    any_change = True
    g = gloss(new)
    known = bool(g) or new in name_index()
    if g:
        verdict = f"CONFIRMED — {new} is a real word ({', '.join(g[:2])})"
    elif new in name_index():
        verdict = f"CONFIRMED — {new} is a known name"
    else:
        verdict = f"REJECTED — {new} is NOT in any dictionary (Qwen may have hallucinated)"
    print(f"  {old or '∅'} -> {new}   | {verdict}")
if not any_change:
    print("  (Qwen made no word-level changes)")

print("\nAUDITOR scan of Qwen's final output (catches what even Qwen missed):")
flags = audit_transcript(corrected).flags
if not flags:
    print("  clean — Qwen's output passes the deterministic checks")
for f in flags:
    print(f"  [{f.rule}] {f.label}")
