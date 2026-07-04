# Path to "perfect" — measured, phase by phase

**Definition of perfect (achievable, testable):** the consensus is the best transcriber available
in every language — it beats any single model — proven on real hard audio, with every data cell full.
(Literal 0.0 WER isn't the target; pro human inter-transcriber agreement is ~92–96%.)

Every phase ships with unit tests AND a bench measurement. A phase is DONE only when the number moves
the right way (or is proven neutral). Baseline to beat (English hard clips, WER, lower better):
single-Deepgram 0.291 · whole-vote 0.240 · token-brain 0.172 · **best single model (Scribe) 0.150**.

## Phase I — Reliability weighting ✅ DONE (2026-07-03) — consensus BEATS best single model
Unweighted votes let a mediocre crowd outvote a proven-strong model. Add per-witness reliability:
steer the UNCERTAIN positions (judge deferred, no family majority) to the most-reliable witness
instead of the medoid; weight family votes by reliability. Surgical — must not regress the clips
the consensus already wins (accent_noise 0.0).
- **DONE:** consensus 0.050 < Scribe 0.068 < single-Deepgram 0.291. accent_noise 0.0 (beats Scribe),
  crosstalk 0.0, propernouns 0.15. Mechanism: reliability-anchored backbone (`_anchor_name`: start from
  the most-accurate witness, refine word-by-word) + prune-garbage-then-reliability word decision
  (`_decide_word`). Note: RELIABILITY priors are English-bench-derived (global) — Phase II calibrates per language.

## Phase II — Measure every language (prove parity, don't assert)
Extend make_hard_battery.py to generate hard clips + ground truth per language; run live_bench.py
for each. **Done when:** every language has a measured consensus-vs-single-model table.

## Phase III — Fill the thin data cells
Leipzig corpora → 9 missing collocation tables; GeoNames/Wikidata → real name gazetteers (replace
the frequency proxy). **Done when:** scanner counts even out and measured accuracy improves.

## Phase IV — Real audio
Record/source real clips per language (not synthetic TTS). **Done when:** the bench holds on real audio.

## Phase V — Legal multilingual (partial)
IATE for EU languages. Honest ceiling — global legal isn't a data download.

Order: I (universal, highest value) → II (prove it) → III/IV/V (data + realism).
