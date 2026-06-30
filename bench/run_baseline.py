#!/usr/bin/env python3
"""Phase 1 baseline — run the engine on the battery, score every witness + the consensus
against ground truth. Produces the scorecard every later phase improves against.

Metrics: WER per witness + consensus (text); diarization-agreement (2-speaker cases).
Also records the consensus agreement % (the 'surfaced uncertainty' half of the 90-95 policy).
"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for l in open(os.path.join(ROOT, ".env")):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

BAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")
cases = sorted(p[:-5] for p in glob.glob(os.path.join(BAT, "*.json")))


def run():
    rows = []
    for cpath in cases:
        name = os.path.basename(cpath)
        ref = json.load(open(cpath + ".json"))
        audio = cpath + ".wav"
        reads = C.roster_panel(audio, "en")                 # all witnesses (hf=402 -> "")
        wers = {m: M.wer(ref["text"], t) for m, t in reads.items() if t}
        vote = C.consensus_vote(reads)
        crep = C.consensus(reads)
        row = {"case": name, "ref_words": len(ref["text"].split()),
               "reads": reads,                            # saved so metric changes don't need re-running
               "wer_by_model": {m: wers[m] for m in sorted(wers)},
               "wer_consensus": M.wer(ref["text"], vote) if vote else None,
               "wer_consensus_raw": M.wer(ref["text"], vote, normalize_numbers=False) if vote else None,
               "consensus_agreement_pct": crep.get("agreement_pct"),
               "n_models": crep.get("n_models")}
        # diarization scoring on the multi-speaker cases
        if len({s["speaker"] for s in ref["speakers"]}) > 1:
            try:
                hyp = C.diarize_long(audio, "en", "scribe")
                dur = max(s["end"] for s in ref["speakers"])
                d = M.diar_agreement(ref["speakers"], hyp, dur=dur)
                row["diar_agreement_pct"] = d["agreement_pct"]
                row["diar_speakers"] = f"{d['hyp_speakers']} vs {d['ref_speakers']} ref"
            except Exception as e:
                row["diar_agreement_pct"] = f"ERR {str(e)[:40]}"
        rows.append(row)
        print(f"  {name:13} consensusWER={row['wer_consensus']}  "
              f"models={row['n_models']}  diar={row.get('diar_agreement_pct','-')}")
    json.dump(rows, open(os.path.join(os.path.dirname(BAT), "baseline.json"), "w"), indent=1)
    print("\nsaved baseline.json")
    return rows


if __name__ == "__main__":
    run()
