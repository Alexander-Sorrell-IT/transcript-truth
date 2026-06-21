"""Controlled catch-rate test: inject a KNOWN homophone error into each gold transcript,
push it through worker(Qwen)->auditor, and measure who catches it.

Per clip: take a correct content word, swap it for a same-reading DIFFERENT word (a real
mishearing). Ground truth is known. Then:
  - worker_fixed: Qwen removed the injected wrong word
  - auditor_caught: Qwen left it, but our deterministic scan flagged it
  - MISS: it survived both
No oracle leakage — we injected the error ourselves.
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.verdict import _toks, gloss, name_index
from transcript_truth.collocation import _homophones, _kata2hira
from transcript_truth.worker import correct_transcript
from transcript_truth.engine import audit_transcript

H = _homophones()
N = int(os.environ.get("N", "30"))
files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sounds", "*.txt")))

worker_fixed = auditor_caught = miss = total = 0
miss_examples = []
for f in files:
    if total >= N:
        break
    gold = open(f, encoding="utf-8").read().strip()
    inj = None
    for m in _toks(gold):
        s = m.surface()
        if len(s) < 2:
            continue
        r = _kata2hira(m.reading_form())
        cands = [c["word"] for c in H.get(r, []) if c["word"] != s]
        if cands:
            inj = (s, cands[0]); break
    if not inj:
        continue
    true_w, wrong_w = inj
    errored = gold.replace(true_w, wrong_w, 1)
    total += 1
    try:
        qout = correct_transcript(errored)
    except Exception as e:
        qout = errored  # worker failed -> treat as no fix
    if wrong_w not in qout:
        worker_fixed += 1
        continue
    # worker left the error -> does the auditor flag it?
    flags = audit_transcript(qout).flags
    hit = any(wrong_w in (fl.evidence or "") or wrong_w in (fl.label or "") for fl in flags)
    if hit:
        auditor_caught += 1
    else:
        miss += 1
        miss_examples.append(f"{true_w}->{wrong_w} (gloss {gloss(wrong_w) or 'non-word' if wrong_w not in name_index() else 'name'})")
    print(f"[{total}] {true_w}->{wrong_w} | worker_fixed={wrong_w not in qout} | "
          f"{'AUDITOR' if (wrong_w in qout and hit) else 'MISS' if wrong_w in qout else 'worker'}", flush=True)

caught = worker_fixed + auditor_caught
print("\n" + "=" * 60)
print(f"injected homophone errors: {total}")
print(f"  caught by WORKER (Qwen fixed)   : {worker_fixed}")
print(f"  caught by AUDITOR (Qwen missed) : {auditor_caught}")
print(f"  MISSED by both                  : {miss}")
print(f"  => system catch rate: {caught}/{total} = {100*caught//max(total,1)}%")
if miss_examples:
    print("  misses:", miss_examples[:8])
