#!/usr/bin/env python3
"""Bench: whole-transcript vote vs NEW token-level (ROVER) vote, scored vs ground truth.

Re-scores the SAVED reads in baseline.json (no new API calls), so it's deterministic and offline.
Compares, per case and in aggregate:
  best_single : lowest WER of any single witness (the single-model ceiling)
  whole_vote  : consensus_vote (whole-transcript, family-aware medoid)   [pre-Phase-B behavior]
  token_vote  : consensus_tokens (per-word ROVER + medoid backstop)      [Phase B]
Lower WER is better. Shows where token-level voting recovers words no single model got right.
"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

BASE = os.path.join(ROOT, "bench", "baseline.json")
BAT = os.path.join(ROOT, "bench", "battery")


def _reads_for_cases():
    """Prefer saved reads (offline); fall back to nothing if baseline.json is absent."""
    if os.path.exists(BASE):
        for row in json.load(open(BASE)):
            ref = json.load(open(os.path.join(BAT, row["case"] + ".json")))
            yield row["case"], ref["text"], {m: t for m, t in row.get("reads", {}).items() if t}


def run():
    rows, agg = [], {"best_single": [], "whole_vote": [], "token_vote": []}
    print(f"  {'case':13} {'best_single':>12} {'whole_vote':>11} {'token_vote':>11}   models")
    print("  " + "-" * 62)
    for case, ref, reads in _reads_for_cases():
        if not reads:
            continue
        best_single = min(M.wer(ref, t) for t in reads.values())
        whole = M.wer(ref, C.consensus_vote(reads))
        token = M.wer(ref, C.consensus_tokens(reads)["text"])
        agg["best_single"].append(best_single)
        agg["whole_vote"].append(whole)
        agg["token_vote"].append(token)
        flag = "  <-- token beats whole" if token < whole else ("  <-- token worse" if token > whole else "")
        print(f"  {case:13} {best_single:>12.4f} {whole:>11.4f} {token:>11.4f}   {len(reads)}{flag}")
        rows.append({"case": case, "best_single": best_single, "whole_vote": whole,
                     "token_vote": token, "n_models": len(reads)})
    if rows:
        n = len(rows)
        mean = lambda k: round(sum(agg[k]) / n, 4)
        print("  " + "-" * 62)
        print(f"  {'MEAN':13} {mean('best_single'):>12.4f} {mean('whole_vote'):>11.4f} {mean('token_vote'):>11.4f}")
        json.dump({"rows": rows,
                   "mean": {k: mean(k) for k in agg}},
                  open(os.path.join(ROOT, "bench", "voting_compare.json"), "w"), indent=1)
        print("\n  saved bench/voting_compare.json")
    else:
        print("  no saved reads found — run bench/run_baseline.py first (needs API keys)")
    return rows


if __name__ == "__main__":
    run()
