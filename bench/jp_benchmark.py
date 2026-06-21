"""Measure the homophone detector's COVERAGE on the workflow's 208 test cases.

The homophone detector is a VISIBILITY tool — it flags that a trap is present, so
the question it answers is coverage: given a sentence containing a known trap, do
we surface it? We compare the 12-entry seed vs the full loaded KB to put a number
on the jump.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.engine import parse_transcript
from transcript_truth.semantic import homophone_traps, ENTRIES, TRAP_COUNT

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cases = json.load(open(os.path.join(REPO, "data", "jp_cases.json"), encoding="utf-8"))

by_key = {e["key"]: e for e in ENTRIES}
# The original hand-seeded keys (what we shipped before the workflow).
SEED_KEYS = {"偏在/遍在", "清算/精算/成算", "保証/保障/補償", "対象/対照/対称",
             "鑑賞/観賞/干渉", "意志/意思", "関心/感心/歓心", "異常/異状"}

homo_cases = [c for c in cases if c.get("target") in by_key]
full_cov = seed_cov = 0
for c in homo_cases:
    members = {k for k, _ in by_key[c["target"]]["members"]}
    flagged = any(f.evidence in members for f in homophone_traps(parse_transcript(c["text"])))
    if flagged:
        full_cov += 1
        if c["target"] in SEED_KEYS:
            seed_cov += 1

# false-positive check: detector must stay silent on clean English / non-trap text
fp = sum(1 for txt in ["Speaker 1: we settle it against the rubric, not by vote.",
                       "?Speaker 2: the call starts at [00:04:12] sharp."]
         if homophone_traps(parse_transcript(txt)))

n = len(homo_cases)
print(f"  KB loaded            : {TRAP_COUNT} homophone trap-sets (was 1 seed-set after filtering)")
print(f"  homophone test cases : {n}")
print(f"  covered by full KB   : {full_cov}/{n}  ({100*full_cov//max(1,n)}%)")
print(f"  would-be seed cover  : {seed_cov}/{n}  ({100*seed_cov//max(1,n)}%)   <- the 8 hand-seeded sets")
print(f"  false positives (EN) : {fp}/2")
print(f"\n  delta: the workflow took homophone coverage {seed_cov} -> {full_cov} cases (+{full_cov-seed_cov}).")
