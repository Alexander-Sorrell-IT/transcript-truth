#!/usr/bin/env python3
"""Run the live full-parity bench on the Urdu clips only and MERGE into full_parity.json
(the stock runner rewrites the whole file; this appends the one missing language)."""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(ROOT, ".env")):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

BAT = os.path.join(ROOT, "bench", "battery")
PAR = os.path.join(ROOT, "bench", "full_parity.json")

results = json.load(open(PAR, encoding="utf-8"))
results = [r for r in results if r["lang"] != "ur"]

for jp in sorted(glob.glob(os.path.join(BAT, "fp_ur*.json"))):
    meta = json.load(open(jp, encoding="utf-8"))
    lang, ref = meta["lang"], meta["text"]
    print(f"[{os.path.basename(jp)}] roster ...", flush=True)
    reads = C.roster_panel(jp[:-5] + ".wav", lang)
    live = {m: t for m, t in reads.items() if t}
    by = {m: round(M.wer(ref, t, lang=lang), 3) for m, t in live.items()}
    best = min(by.values()) if by else None
    con = round(M.wer(ref, C.consensus_tokens(reads, lang)["text"], lang=lang), 3)
    results.append({"lang": lang, "consensus": con, "best_single": best,
                    "best_model": (min(by, key=by.get) if by else None),
                    "wins": best is None or con <= best + 1e-9,
                    "wer_by_model": by, "reads": live, "clip": jp[:-5] + ".wav"})
    print(f"    consensus={con} best={best} by={by}", flush=True)

json.dump(results, open(PAR, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ur = [r for r in results if r["lang"] == "ur"]
print(f"\nUR: avg consensus {sum(r['consensus'] for r in ur)/len(ur):.3f} over {len(ur)} clips", flush=True)
