#!/usr/bin/env python3
"""Phase III.1 validation: WER before/after the contested-span re-ask loop, on the trailing
languages' hard clips. Uses SAVED first-pass reads (no re-transcribe cost) + live re-ask slices."""
import os, sys, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(ROOT, ".env")):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M
from transcript_truth.reask import reask_contested

LANGS = set(sys.argv[1:]) or {"tr", "ar", "ur"}
rows = [r for r in json.load(open(os.path.join(ROOT, "bench", "full_parity.json")))
        if r["lang"] in LANGS and "clip" in r]

before, after, fixes = [], [], []
for r in rows:
    stem = os.path.basename(r["clip"]).rsplit(".", 1)[0]
    wav = os.path.join(ROOT, "bench", "battery", stem + ".wav")
    truth = json.load(open(os.path.join(ROOT, "bench", "battery", stem + ".json")))["text"]
    res = C.consensus_tokens(r["reads"], r["lang"])
    b = M.wer(truth, res["text"], lang=r["lang"])
    res2 = reask_contested(wav, r["reads"], r["lang"], res)
    a = M.wer(truth, res2["text"], lang=r["lang"])
    before.append(b); after.append(a)
    for s in res2["uncertain_spans"]:
        if s.get("by") == "reask":
            fixes.append((r["lang"], stem, s["from"], "->", s["to"]))
    print(f"{stem:10} [{r['lang']}] {b:.3f} -> {a:.3f}", flush=True)

print(f"\nBEFORE {sum(before)/len(before):.4f}  AFTER {sum(after)/len(after):.4f}  "
      f"({sum(1 for x, y in zip(before, after) if y < x)} improved, "
      f"{sum(1 for x, y in zip(before, after) if y > x)} regressed)")
for f in fixes:
    print(" reask:", *f)
