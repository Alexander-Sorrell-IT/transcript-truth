#!/usr/bin/env python3
"""Score the translation battery vs recovered English references (ROADMAP Phase 8, task 1 — the gate).

Joins bench/translation_bench.json (engine outputs) to bench/fleurs_en_refs.json (English parallels
recovered by fleurs_en_refs.py) and reports the honest X->EN parity number using the SAME ruler as
transcription: metrics.wer (word) + metrics.cer (per-character, cross-script comparable). Reports
overall + per-language, and — the point of the flag policy — parity on the CONFIDENT (unflagged)
subset vs the FLAGGED subset, so we can see whether the honest-uncertainty flag actually separates
good translations from bad ones.

    python3 bench/translation_score.py

No API calls — pure offline scoring of saved outputs. A clip with no recovered reference is skipped
and counted (never scored against a fabricated reference).
"""
import os, sys, json, statistics as st
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from transcript_truth.metrics import wer, cer
from transcript_truth.translate import _run_qa_safe, _qa_has_hard_flag as _qa_hard


def chrf(ref: str, hyp: str, n: int = 6, beta: float = 2.0) -> float:
    """chrF (Popović 2015) — the MT-standard char-n-gram F-score, HIGHER is better (0..1). Unlike
    WER it is paraphrase-tolerant: it rewards shared character n-grams, so a faithful translation
    that reorders words or swaps a synonym is not punished the way exact-word WER punishes it. This
    is the honest translation-quality ruler; WER stays as a strictness/divergence secondary signal."""
    def ngrams(s, k):
        s = s.strip()
        return Counter(s[i:i + k] for i in range(len(s) - k + 1)) if len(s) >= k else Counter()
    ps, rs = [], []
    for k in range(1, n + 1):
        h, r = ngrams(hyp, k), ngrams(ref, k)
        match = sum((h & r).values())
        if sum(h.values()):
            ps.append(match / sum(h.values()))
        if sum(r.values()):
            rs.append(match / sum(r.values()))
    if not ps or not rs:
        return 0.0
    chrp, chrr = st.mean(ps), st.mean(rs)
    if chrp + chrr == 0:
        return 0.0
    b2 = beta * beta
    return round((1 + b2) * chrp * chrr / (b2 * chrp + chrr), 3)

BENCH = os.path.join(ROOT, "bench")
OUTS = json.load(open(os.path.join(BENCH, "translation_bench.json"), encoding="utf-8"))
REFS = json.load(open(os.path.join(BENCH, "fleurs_en_refs.json"), encoding="utf-8")) \
    if os.path.exists(os.path.join(BENCH, "fleurs_en_refs.json")) else {}


def summarize(rows, label):
    if not rows:
        print(f"  {label:<22} (no scored clips)")
        return
    f = st.mean(r["chrf"] for r in rows)
    w = st.mean(r["wer"] for r in rows)
    print(f"  {label:<22} n={len(rows):<3} chrF={f:.3f} (↑)   WER={w:.3f} (↓)")


def main():
    if not REFS:
        print("No references yet. Run:  python3 bench/fleurs_en_refs.py")
        return 1
    scored, skipped = [], []
    for o in OUTS:
        stem = o.get("stem") or os.path.basename(o["clip"]).rsplit(".", 1)[0]
        ref = REFS.get(stem)
        hyp = o.get("text") or ""
        if not ref or not hyp:
            skipped.append(stem)
            continue
        en = ref["en"]
        # Recompute the headline flag under the CURRENT logic (offline): the QA control is purely
        # additive, so new_flagged = saved_flagged OR run_qa-hard-flag on the (source, translation)
        # pair. This re-scores the confident/flagged split AND surfaces any clip the new passthrough
        # /leak control newly flags — the FP check the offline build could not run.
        qa = _run_qa_safe(o.get("transcript") or "", hyp, o["lang"], "en")
        qa_hard = _qa_hard(qa)
        new_flagged = bool(o.get("flagged")) or qa_hard
        scored.append({"stem": stem, "lang": o["lang"],
                       "flagged": new_flagged, "was_flagged": bool(o.get("flagged")),
                       "qa_newly_flagged": qa_hard and not bool(o.get("flagged")),
                       "chrf": chrf(en, hyp), "wer": wer(en, hyp), "cer": cer(en, hyp),
                       "agreement": o.get("agreement")})

    print(f"\nTranslation X->EN parity  ({len(scored)} scored, {len(skipped)} skipped for no ref)\n")
    summarize(scored, "ALL")
    print()
    for lang in sorted({r["lang"] for r in scored}):
        summarize([r for r in scored if r["lang"] == lang], f"lang={lang}")
    print("\n  --- does the honest-uncertainty flag separate good from bad? (current logic) ---")
    summarize([r for r in scored if not r["flagged"]], "CONFIDENT (unflagged)")
    summarize([r for r in scored if r["flagged"]], "FLAGGED (for review)")
    newly = [r for r in scored if r.get("qa_newly_flagged")]
    if newly:
        print(f"\n  QA control newly flags {len(newly)} clip(s) the old logic missed "
              f"(inspect for false positives):")
        for r in newly:
            print(f"    {r['stem']} ({r['lang']}) chrF={r['chrf']:.3f} — "
                  f"{'LOW quality, correct flag' if r['chrf'] < 0.55 else 'check: possible FP'}")
    if skipped:
        print(f"\n  skipped (no reference): {', '.join(skipped)}")
    # persist the scorecard for re-reading without recompute
    out = os.path.join(BENCH, "translation_scorecard.json")
    json.dump({"scored": scored, "skipped": skipped}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
