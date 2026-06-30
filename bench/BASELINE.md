# Phase 1 — Baseline scorecard (2026-06-30)

Battery: 6 TTS-generated cases with exact ground truth (`bench/battery/`, regenerate with
`make_battery.py`, score with `run_baseline.py`). TTS audio is cleaner than real-world speech,
so these are an **upper bound / pipeline check** — real hard clips get added to the same battery later.

WER is **number-aware** (canonicalizes %/$/dates/years so "15%"≡"fifteen percent" — measures words,
not style). Raw WER also recorded in `baseline.json` (`wer_consensus_raw`).

| Case | WER (consensus) | Diarization | What it shows |
|---|---|---|---|
| clean | **0.0** | — | Perfect content (raw 0.167 was just "15%" vs "fifteen percent") |
| fast (1.5×) | **0.0** | — | Robust to speed |
| noisy (pink) | **0.0** | — | Robust to moderate noise |
| numbers | **0.056** (94.4%) | — | One real error: "Eleanor"→"Elena" (an uncommon proper name) |
| two_seq | **0.0** | **100%** | Sequential 2-speaker: perfect |
| two_overlap | **0.0** | **90%** | Crosstalk: text perfect, diarization 90% (measured cost of overlap) |

All cases reached **3-model consensus** (Deepgram + Gemini + Scribe; HF = 402 out of credits).
Raw reads are saved in `baseline.json`, so metric changes can be re-scored with **no new API calls**.

## Baseline numbers to beat
- **Text (number-aware WER):** 0.0 on clean/fast/noisy/2-speaker; **0.056 on proper-nouns** (the frontier).
- **Diarization:** **100% sequential / 90% crosstalk.**
- These are on clean TTS audio (upper bound). Real hard clips will lower them — that's the point of the battery.

## Two findings the baseline surfaced (actionable)
1. **Raw WER over-counts because of number/date/currency formatting** ("15%" vs "fifteen percent",
   "$47 million" vs "forty-seven million dollar"). For a transcription job this is a **style-guide
   choice**, not an error. → *Metric refinement:* add number-aware normalization to `metrics.wer`
   so it scores WORDS, not formatting. Until then, read raw WER as an upper bound.
2. **The real accuracy frontier is uncommon proper nouns** (the name error). This is exactly where
   multi-model consensus + `[phonetic]` flagging + a future name-lexicon should earn their keep.

## Honest read
On clean/fast/noisy speech the engine is **near-perfect on content** (the WER is formatting).
Diarization is **100% sequential / 90% crosstalk**. The genuine weak spot is **proper nouns**.
This is the number every later phase improves against — and it confirms the 90-95% policy:
surface the uncertain proper nouns rather than guess them.
