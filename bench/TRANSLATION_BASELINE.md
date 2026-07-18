# Translation-track baseline (ROADMAP Phase 8, task 1 — the gate)

Measured 2026-07-17. The honest X→EN parity of the translation track, scored against FLEURS human
reference translations recovered by FLoRes sentence id.

## How it was measured
- `bench/translation_bench.py` — ran `translate()` over 30 real-audio clips (tr/ar/hi/ur/vi/ja ×5),
  each a two-witness translation (SeamlessM4T S2TT from audio + Gemini over the measured transcript)
  with the deterministic survival-check verdict. Outputs saved (no re-run needed to re-score).
- `bench/fleurs_en_refs.py` — recovered the English parallel for every clip: FLEURS is parallel via
  the FLoRes sentence `id`, shared across all language configs, so each source clip's id maps to the
  en_us English text. 60 refs recovered, resumable (`fleurs_ids.json` cache).
- `bench/translation_score.py` — joins outputs↔refs and scores.

## The ruler (important)
WER — the transcription ruler — **over-penalizes translation**: there are many valid ways to render a
sentence, and WER counts every word-order or synonym difference vs one reference as an error. Observed:
a fully faithful translation ("We make our homes and clothes from plants…") scored **WER 0.54** purely
from paraphrase divergence. So the honest translation ruler is **chrF** (Popović 2015, char-n-gram F,
paraphrase-tolerant, the MT standard); WER is kept as a secondary strictness signal.

## Result — overall chrF 0.618  (↑ better)

| lang | chrF ↑ | WER ↓ | notes |
|------|-------|-------|-------|
| ar   | 0.736 | 0.423 | strongest |
| hi   | 0.723 | 0.433 | strongest |
| tr   | 0.657 | 0.431 | |
| ur   | 0.565 | 0.677 | weak |
| vi   | 0.547 | 0.698 | weak |
| ja   | 0.481 | 0.747 | weakest — same as the transcription map |
| **ALL** | **0.618** | 0.568 | |

The difficulty ordering matches the transcription real-audio parity map — the languages that are hard
to *hear* are hard to *translate*, as expected.

## The honest-uncertainty flag separates good from bad (chrF/WER, n=15)
The whole philosophy is: never silently guess — surface uncertainty. On this bench the flag separates:

| subset | chrF ↑ | WER ↓ |
|--------|-------|-------|
| CONFIDENT (unflagged) | 0.656 | 0.541 |
| FLAGGED (for review)  | 0.580 | 0.595 |

Confident translations score better than flagged ones on BOTH chrF and WER. Honest caveats: n=15 per
side, single reference, and CER (a third ruler) was near-flat/slightly reversed (0.461 vs 0.426) — so
this is "separates on chrF/WER at this sample size," not a proven law. The direction is right; the
magnitude needs more clips.

**The translation-QA control is real, not decorative (verified 2026-07-18).** `run_qa` hard flags
(source-script leak, same-script untranslated passthrough, glossary miss, gross length anomaly) now
drive the HEADLINE `flagged` verdict, not just the review surface — unit-proven to flip `flagged=True`
on a synthetic es→en passthrough and an ar→en script leak, and to leave a clean translation unflagged.
On the 30 real bench clips it adds **zero** new flags (the real witnesses genuinely translate), i.e.
zero false positives — the FP check the offline build could not run.

## Known weak spots → the next tasks
- **ja / vi / ur** are the low end — the specialized-witness path (like transcription Phase 5).
- **Latin-script name errors slip through unflagged** — e.g. "Spring Book" for "Springboks" scored a
  bad clip but was NOT flagged. Targets: name-survival hardening + the translation-QA layer
  (source-script leak, length-ratio) — ROADMAP Phase 8 tasks 3–4.

Re-score any time with no API calls: `python3 bench/translation_score.py`.
