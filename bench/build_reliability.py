#!/usr/bin/env python3
"""Derive PER-LANGUAGE witness reliability from the measured full-parity bench (multi-clip):
data/witness_reliability.json = {lang: {model: 1 - mean_WER}}. This is the data cell that lets the
vote know 'deepgram is the Turkish anchor / gemini is bad at Turkish' — measured, never hand-set.
Requires >=2 clips per language to write an entry (no tuning on a single sentence)."""
import os, sys, json, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "bench", "full_parity.json")
OUT = os.path.join(ROOT, "data", "witness_reliability.json")

MIN_CLIPS = 2

rows = json.load(open(SRC, encoding="utf-8"))
acc = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    for m, w in r["wer_by_model"].items():
        acc[r["lang"]][m.split("@", 1)[0]].append(w)

out = {}
for lang, models in sorted(acc.items()):
    n_clips = max(len(v) for v in models.values())
    if n_clips < MIN_CLIPS:
        print(f"  {lang}: only {n_clips} clip(s) — skipped (no N=1 tuning)")
        continue
    out[lang] = {m: round(max(0.0, 1.0 - sum(v) / len(v)), 3)
                 for m, v in models.items() if len(v) >= MIN_CLIPS}
    print(f"  {lang}: " + " ".join(f"{m}={w}" for m, w in
                                   sorted(out[lang].items(), key=lambda x: -x[1])))

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print(f"-> {OUT} ({len(out)} languages)")
