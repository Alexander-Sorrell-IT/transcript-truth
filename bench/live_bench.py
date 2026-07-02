#!/usr/bin/env python3
"""LIVE end-to-end bench: single-model vs multi-model on the HARD clips (needs API keys in .env).

For each hard_* clip this runs the REAL roster (live witnesses + on-demand local tier), then scores
against ground truth:
  deepgram_only : Deepgram's own read  = the single-model baseline (what runner used before Phase H)
  whole_vote    : consensus_vote (whole-transcript, family-aware)
  token_vote    : consensus_tokens (per-word ROVER)   <- the Phase B win
Lower WER better. Writes bench/live_results.json. Run:  python3 -u bench/live_bench.py
"""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(ROOT, ".env")):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

BAT = os.path.join(ROOT, "bench", "battery")
CLIPS = sorted(glob.glob(os.path.join(BAT, "hard_*.json")))


def run():
    results = []
    for jp in CLIPS:
        case = os.path.basename(jp)[:-5]
        ref = json.load(open(jp))["text"]
        audio = jp[:-5] + ".wav"
        print(f"[{case}] running live roster ...", flush=True)
        reads = C.roster_panel(audio, "en")
        live = {m: t for m, t in reads.items() if t}
        dg = reads.get("deepgram", "")
        row = {
            "case": case,
            "witnesses": sorted(live),
            "wer_by_model": {m: round(M.wer(ref, t), 4) for m, t in live.items()},
            "deepgram_only": round(M.wer(ref, dg), 4) if dg else None,
            "whole_vote": round(M.wer(ref, C.consensus_vote(reads)), 4),
            "token_vote": round(M.wer(ref, C.consensus_tokens(reads)["text"]), 4),
            "reads": live,
        }
        results.append(row)
        print(f"    witnesses={row['witnesses']}", flush=True)
        print(f"    deepgram_only={row['deepgram_only']}  whole={row['whole_vote']}  "
              f"token={row['token_vote']}", flush=True)

    out = os.path.join(ROOT, "bench", "live_results.json")
    json.dump(results, open(out, "w"), indent=1)

    def mean(k):
        vals = [r[k] for r in results if r.get(k) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None
    print("\n=== SUMMARY (WER, lower=better) ===", flush=True)
    print(f"  {'case':20} {'single(dg)':>11} {'whole':>8} {'token':>8}", flush=True)
    for r in results:
        print(f"  {r['case']:20} {str(r['deepgram_only']):>11} {r['whole_vote']:>8} {r['token_vote']:>8}",
              flush=True)
    print(f"  {'MEAN':20} {str(mean('deepgram_only')):>11} {mean('whole_vote'):>8} {mean('token_vote'):>8}",
          flush=True)
    print(f"\nsaved {out}", flush=True)


if __name__ == "__main__":
    run()
