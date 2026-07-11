#!/usr/bin/env python3
"""Phase IV — the REAL-AUDIO map: run the roster + consensus (incl. TIER-3 re-ask) on the FLEURS
battery and score with the one ruler. Saves reads to bench/real_audio.json so metric changes
re-score offline with no new API calls (same pattern as full_parity.json).

    python3 bench/live_bench_real.py [lang ...]
"""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for line in open(os.path.join(ROOT, ".env")):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M
from transcript_truth.reask import reask_contested

BAT = os.path.join(ROOT, "bench", "battery_real")
OUT = os.path.join(ROOT, "bench", "real_audio.json")

langs = set(sys.argv[1:])
results = []
if os.path.exists(OUT):
    results = [r for r in json.load(open(OUT, encoding="utf-8"))
               if not langs or r["lang"] not in langs]
done = {r["clip"] for r in results}

clips = sorted(glob.glob(os.path.join(BAT, "rl_*.json")))
for jp in clips:
    meta = json.load(open(jp, encoding="utf-8"))
    lang, ref = meta["lang"], meta["text"]
    wav = jp[:-5] + ".wav"
    if (langs and lang not in langs) or wav in done:
        continue
    print(f"[{os.path.basename(wav)}] roster …", flush=True)
    reads = C.roster_panel(wav, lang)
    live = {m: t for m, t in reads.items() if t}
    by = {m: round(M.wer(ref, t, lang=lang), 3) for m, t in live.items()}
    res = C.consensus_tokens(reads, lang)
    res = reask_contested(wav, reads, lang, res)
    con = round(M.wer(ref, res["text"], lang=lang), 3)
    cer = round(M.cer(ref, res["text"], lang=lang), 3)
    best = min(by.values()) if by else None
    results.append({"lang": lang, "clip": wav, "consensus": con, "cer": cer,
                    "best_single": best,
                    "best_model": (min(by, key=by.get) if by else None),
                    "wer_by_model": by, "reads": live,
                    "reask_fires": sum(1 for s in res["uncertain_spans"]
                                       if s.get("by") == "reask")})
    print(f"    wer={con} cer={cer} best={best}", flush=True)
    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

from collections import defaultdict
agg, agg_c = defaultdict(list), defaultdict(list)
for r in results:
    agg[r["lang"]].append(r["consensus"]); agg_c[r["lang"]].append(r["cer"])
print("\n=== REAL-AUDIO MAP (FLEURS, human speech) ===")
print(f"{'lang':5} {'WER':>7} {'CER':>7} {'n':>3}")
for l in sorted(agg, key=lambda x: sum(agg_c[x]) / len(agg_c[x])):
    print(f"{l:5} {sum(agg[l])/len(agg[l]):7.3f} {sum(agg_c[l])/len(agg_c[l]):7.3f} {len(agg[l]):3}")
