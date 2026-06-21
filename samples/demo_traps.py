import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.engine import parse_transcript
from transcript_truth.semantic import homophone_traps

CASES = [
    ("Q8  (the sentence that beat me)", "Interviewer: 昨今我が国で当たり前のように偏在していたものが、当たり前でなくなってきている。"),
    ("Q9", "Interviewee: やっぱり罪を犯した彼には、更生施設に入り、罪の清算をしていってほしいと願います。"),
    ("English control", "Speaker 1: We settle every divergence against the rubric, not by majority vote."),
]

for label, text in CASES:
    flags = homophone_traps(parse_transcript(text))
    print(f"\n=== {label} — {len(flags)} trap(s) flagged ===")
    for f in flags:
        print(f"  [{f.evidence}]  {f.fix}")
