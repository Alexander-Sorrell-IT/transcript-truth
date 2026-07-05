#!/usr/bin/env python3
"""Incremental full-parity bench: run ONLY clips not yet in bench/full_parity.json (plus any
language listed in FORCE_LANGS, whose roster changed), merge results, save. Keyed by clip path
so the battery can grow without re-paying for measured clips."""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(ROOT, ".env")):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

FORCE_LANGS = set((os.environ.get("FORCE_LANGS") or "").split(",")) - {""}
OUT = os.path.join(ROOT, "bench", "full_parity.json")
BAT = os.path.join(ROOT, "bench", "battery")

old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
# legacy rows have no 'clip' key — reconstruct from the sorted order they were run in
legacy_clips = sorted(glob.glob(os.path.join(BAT, "fp_*.json")))[:len(old)] if old and "clip" not in old[0] else None
if legacy_clips:
    for r, p in zip(old, legacy_clips):
        r["clip"] = os.path.basename(p)
done = {r["clip"] for r in old if r["lang"] not in FORCE_LANGS}
keep = [r for r in old if r["clip"] in done]

results = list(keep)
for jp in sorted(glob.glob(os.path.join(BAT, "fp_*.json"))):
    clip = os.path.basename(jp)
    if clip in done:
        continue
    meta = json.load(open(jp, encoding="utf-8"))
    lang, ref = meta["lang"], meta["text"]
    print(f"[{clip}] roster ...", flush=True)
    reads = C.roster_panel(jp[:-5] + ".wav", lang)
    live = {m: t for m, t in reads.items() if t}
    by = {m: round(M.wer(ref, t, lang=lang), 3) for m, t in live.items()}
    best = min(by.values()) if by else None
    con = round(M.wer(ref, C.consensus_tokens(reads, lang)["text"], lang=lang), 3)
    results.append({"clip": clip, "lang": lang, "consensus": con, "best_single": best,
                    "best_model": (min(by, key=by.get) if by else None),
                    "wins": best is None or con <= best + 1e-9, "wer_by_model": by, "reads": live})
    print(f"    consensus={con} best={best} {'WIN/tie' if results[-1]['wins'] else 'BEHIND'}", flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:      # checkpoint after every clip
        json.dump(results, fh, ensure_ascii=False, indent=1)

wins = sum(r["wins"] for r in results)
print(f"\nPARITY: {wins}/{len(results)} clips WIN/tie", flush=True)
