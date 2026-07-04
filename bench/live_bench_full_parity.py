#!/usr/bin/env python3
"""FULL-PARITY live bench: run the real roster on EVERY language's hard clip (fp_*), score consensus
vs best single model (number-format-neutral WER). This is the whole map — every language held to the
same bar, measured not asserted. Saves reads so re-scoring is free. Writes bench/full_parity.json.
"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(ROOT, ".env")):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

BAT = os.path.join(ROOT, "bench", "battery")
CLIPS = sorted(glob.glob(os.path.join(BAT, "fp_*.json")))


def run():
    results = []
    for jp in CLIPS:
        meta = json.load(open(jp, encoding="utf-8"))
        lang, ref = meta["lang"], meta["text"]
        print(f"[{lang}] roster ...", flush=True)
        reads = C.roster_panel(jp[:-5] + ".wav", lang)
        live = {m: t for m, t in reads.items() if t}
        by = {m: round(M.wer(ref, t, lang=lang), 3) for m, t in live.items()}
        best = min(by.values()) if by else None
        con = round(M.wer(ref, C.consensus_tokens(reads, lang)["text"], lang=lang), 3)
        row = {"lang": lang, "consensus": con, "best_single": best,
               "best_model": (min(by, key=by.get) if by else None),
               "wins": best is None or con <= best + 1e-9, "wer_by_model": by, "reads": live}
        results.append(row)
        print(f"    consensus={con} best={best} {'WIN/tie' if row['wins'] else 'BEHIND'}", flush=True)

    with open(os.path.join(ROOT, "bench", "full_parity.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    wins = sum(r["wins"] for r in results)
    print("\n=== FULL PARITY MAP (number-neutral WER) ===", flush=True)
    print(f"  {'lang':5} {'consensus':>10} {'best_single':>12} {'verdict':>9}", flush=True)
    for r in sorted(results, key=lambda x: x["lang"]):
        print(f"  {r['lang']:5} {r['consensus']:>10} {str(r['best_single'])+'('+str(r['best_model'])+')':>12} "
              f"{'WIN/tie' if r['wins'] else 'BEHIND':>9}", flush=True)
    print(f"\n  PARITY: consensus >= best single in {wins}/{len(results)} languages", flush=True)


if __name__ == "__main__":
    run()
