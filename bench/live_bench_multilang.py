#!/usr/bin/env python3
"""LIVE multilingual bench (Phase II): run the real roster per language, score consensus vs the
best single model against ground truth. Proves per-language parity — the reliability priors were
English-derived, so this checks they hold elsewhere. Writes bench/live_multilang.json. Run with -u.
"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(ROOT, ".env")):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

BAT = os.path.join(ROOT, "bench", "battery")
CLIPS = sorted(glob.glob(os.path.join(BAT, "ml_*.json")))


def run():
    results = []
    for jp in CLIPS:
        meta = json.load(open(jp, encoding="utf-8"))
        lang, ref = meta["lang"], meta["text"]
        audio = jp[:-5] + ".wav"
        print(f"[{lang}] running roster ...", flush=True)
        reads = C.roster_panel(audio, lang)
        live = {m: t for m, t in reads.items() if t}
        by = {m: round(M.wer(ref, t), 3) for m, t in live.items()}
        best_single = min(by.values()) if by else None
        best_model = min(by, key=by.get) if by else None
        consensus = round(M.wer(ref, C.consensus_tokens(reads, lang)["text"]), 3)
        row = {"lang": lang, "witnesses": sorted(live), "wer_by_model": by,
               "best_single": best_single, "best_model": best_model, "consensus": consensus,
               "consensus_wins": (best_single is None) or (consensus <= best_single),
               "reads": live}   # saved so metric/priors changes re-score with no new API calls
        results.append(row)
        print(f"    consensus={consensus}  best_single={best_single}({best_model})  "
              f"{'WIN/tie' if row['consensus_wins'] else 'BEHIND'}", flush=True)

    with open(os.path.join(ROOT, "bench", "live_multilang.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print("\n=== SUMMARY (WER) ===", flush=True)
    print(f"  {'lang':5} {'consensus':>10} {'best_single':>12} {'verdict':>9}", flush=True)
    wins = 0
    for r in results:
        wins += r["consensus_wins"]
        print(f"  {r['lang']:5} {r['consensus']:>10} "
              f"{str(r['best_single'])+'('+str(r['best_model'])+')':>12} "
              f"{'WIN/tie' if r['consensus_wins'] else 'BEHIND':>9}", flush=True)
    print(f"\n  consensus >= best single model in {wins}/{len(results)} languages", flush=True)


if __name__ == "__main__":
    run()
