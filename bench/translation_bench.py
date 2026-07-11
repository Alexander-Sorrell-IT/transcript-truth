#!/usr/bin/env python3
"""Translation-track bench (ROADMAP Phase 8 validation): run translate() over the REAL-audio
battery using SAVED consensus transcripts (no re-transcription), store every output in
bench/translation_bench.json for offline scoring against FLEURS parallel English references.

    python3 bench/translation_bench.py [n_per_lang] [lang ...]

Serial by design: SeamlessM4T is a single ~9GB local model — one instance, one process.
Incremental: already-benched clips are skipped, so reruns only fill gaps (gemini 429 recovery).
"""
import os, sys, json, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for line in open(os.path.join(ROOT, ".env")):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C
from transcript_truth.translate import translate

OUT = os.path.join(ROOT, "bench", "translation_bench.json")
n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5
langs = [a for a in sys.argv[1:] if not a.isdigit()] or ["tr", "ar", "hi", "ur", "vi", "ja"]

rows = json.load(open(os.path.join(ROOT, "bench", "real_audio.json"), encoding="utf-8"))
results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
done = {r["clip"] for r in results}

per_lang = {}
for r in rows:
    if r["lang"] not in langs or r["clip"] in done:
        continue
    if per_lang.get(r["lang"], 0) >= n:
        continue
    per_lang[r["lang"]] = per_lang.get(r["lang"], 0) + 1
    stem = os.path.basename(r["clip"]).rsplit(".", 1)[0]
    print(f"[{stem}] translate {r['lang']} -> en …", flush=True)
    tx = C.consensus_tokens(r["reads"], r["lang"])["text"]
    res = translate(r["clip"], r["lang"], "en", transcript=tx)
    results.append({"clip": r["clip"], "stem": stem, "lang": r["lang"],
                    "transcript": tx, **{k: res[k] for k in
                    ("text", "alt", "agreement", "flagged", "checks", "checks_alt")}})
    print(f"    agree={res['agreement']} flagged={res['flagged']}"
          f" text={res['text'][:80]!r}", flush=True)
    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    time.sleep(3)   # pace gemini (free tier rate limits)

print(f"\n{len(results)} clips benched -> {OUT}")
