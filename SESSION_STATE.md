# transcript-truth — session state (2026-07-05)

## REAL parity push (2026-07-05) — measure, then fill the JA-gap with DATA, not hand-tuning
- **Live full-parity bench re-run:** honest map was 8/12 WIN/tie (BEHIND: ar 0.438/0.312, hi 0.143/0.029,
  tr 0.25/0.083, pt 0.095/0.048 — the vote actively WORSE than the best single model there).
- **Root causes (diffed consensus vs best reads):** every loss was a PROPER-NOUN loss
  ('Kagiso'->कागजों/Cajizo, 'Nguyen' dropped). Old gazetteer = 391k, places-only (cities15000,
  no PPLX, no PEOPLE). JA never hits this because JMnedict has 954k names.
- **Fixes (all data / general-mechanism; commits 5a9a9d5, dc06111, 97b04a4):**
  1. Gazetteer rebuilt: cities500 + names-dataset (1.47M person names) = **2.6M surfaces** +
     cross-script romanized lookup (unidecode + repeat-collapse: कागिसो -> kagiso).
  2. Word-vs-name split (`_is_word` vs `_is_known`): the fat gazetteer contains surname-shaped
     misspellings ('Thier'), so a name-only near-variant (ratio>=0.75) of a competing DICT word
     is demoted — keeps "their beats thier" while keeping Kagiso/कागिसो alive.
  3. Korean lexicon was FAKE (wordfreq averages syllables; garble scored zipf 4.27) -> real
     mecab-ko-dic morpheme-coverage backend.
  4. Collocation cells for ALL 9 missing langs (fr de pt tr ko vi ar hi ur) via ONE generic
     builder (`bench/build_collocations_multilang.py`): Wikipedia stream, corpus-share stopwords
     (self-calibrating), \p{L}\p{M} tokenizer (stdlib re shreds Devanagari at matras).
- **RESULT (re-scored on saved reads): parity 10/12** — hi 0.143->0.029 (=best), pt 0.095->0.048 (=best),
  uk 0.143->0.071 (**consensus now BEATS its best single**). Suite 346 green.
- **Still BEHIND:** tr (vote drops 'Nguyen'; deepgram is the lone good witness — needs per-language
  reliability weighting) and ar (ALL 4 witnesses bad 0.31-0.44 — needs a better Arabic roster).

## Gap-close round 2 (2026-07-05, commit 7b92e17) — 48-clip measured verdict
- **Battery 4x'd:** `bench/make_full_parity_battery2.py` adds 3 clips/lang (different names/numbers)
  -> 48 hard clips. Full live bench re-run on all of them (bench/fp_run2.log, full_parity.json).
- **RESULT: 42/48 clips WIN/tie.** Per lang: ja ko fr hi ru uk vi = 4/4 (hi was the worst language
  a day ago); de es pt ar = 3/4; tr = 2/4. ar improved via Whisper(hf) added to roster.
- **Per-language reliability MEASURED** (`bench/build_reliability.py` -> data/witness_reliability.json,
  >=2 clips required). Wired via `_reliability(name, lang)`; used ONLY in _decide_word. Anchor selection
  keeps the GLOBAL prior — measured: per-lang anchor flips on slivers and LOSES clips (41/48 vs 42/48).
- **N=1 lesson proven:** the 'deepgram is the tr anchor' theory from 1 clip was WRONG — over 4 clips
  scribe averages best in tr. Never tune on one sentence.
- **Remaining honest gaps:** tr 2/4 (consensus mean 0.29 vs best 0.247 — small); ar mean 0.295 = tie
  (every witness still bad: best ar witness hf=0.575 reliability; needs a real Arabic ASR model);
  de/es/pt each dropped 1 clip on formatting-ish diffs. Suite 346 green.

Single source of truth for where we are. Companion docs: `ROADMAP.md` (plan + per-phase status),
`MODELS.md` (model strategy + install), `bench/BASELINE.md` (measured scorecard).

## Phases (of 9)
- **Phase 0 — long-audio multi-model core: ✅ DONE.** Chunking (VAD-aware + fixed fallback, fuzzy splice, bad_seams=0), roster-agnostic `consensus()`, robust whole-file diarization, **reference-map diarization 95.8%**, cross-diarizer consensus + graceful witness drop.
- **Phase 1 — measurement: ✅ CORE DONE.** `metrics.py` (number-aware WER + diar-agreement), 6-case TTS battery w/ ground truth, baseline scorecard. Follow-up: real hard clips, make 90-95 a hard gate.
- **Phase 2 — auto-detect + routing: ✅ DONE.** `language.detect/route/profile_for/script_of`, `runner.transcribe_auto`. Verified en+ja+fr live.
- **Phase 3 — Tier-1 langs: ✅ DONE.** French, German, Portuguese, Turkish (each: lexicon + crown-jewel rule + ROSTER + tests).
- **Phase 4 — Tier-2 langs: ✅ DONE.** Korean (batchim particle check via Kiwi), Vietnamese (f/j/w/z). Both validated live.
- **Phase 5 — Tier-3 langs: 🟡 PROFILES DONE.** Arabic, Hindi, Urdu profiles+rules+routing+tests done; **witness ASR quality not yet battery-validated** (the real Phase-5 work).
- **Phases 6 (code-switching), 7 (adversarial agents), 8 (translation EN→X): ⬜ not started.**

**11 languages live:** ja, en, es, ru, uk, fr, de, pt, tr, ko, vi (+ ar, hi, ur profiles). **220 tests passing, 0 failing** (see Testing below).

## Multi-model upgrades (see MODEL_MAP.md + IMPLEMENTATION_PLAN.md, 8 phases A–H)
- **PER-LANGUAGE PARITY PROVEN (2026-07-03):** probed the adjudicator in all 14 languages; found +
  fixed 3 real gaps — Turkish İ casefolding (`.lower()` -> combining U+0307; `_clean` now strips it),
  Korean tokenization (**needs `pip install mecab-ko-dic mecab-python3`** for wordfreq ko), and Japanese
  now uses its native JMdict + 954k-name JMnedict gazetteer (via verdict) instead of generic wordfreq.
  All 14 langs now: real word/name beats pure garble (override), two real words DEFER (safe). 28 parity
  tests (`test_parity_languages.py`), 14 langs x 2 properties. Suite 344 green.
- **The 'brain' — deterministic adjudicator (2026-07-03):** `adjudicate.py` scores each candidate
  word by deterministic linguistic validity (lexicon real-word) + collocation fit, wired into
  `consensus_tokens(reads, lang)` as the FIRST decider: a real word beats a mis-heard NON-word even
  as a lone minority (proven: 2 models agree 'thier', judge picks scribe's 'their'). CONSERVATIVE —
  overrides ONLY on validity (never swaps one valid word for another; the bench caught + we fixed a
  'waiting on'->'waiting for' regression). Safe on hard clips (never worse). FRONTIER: proper nouns
  aren't in fixed dictionaries — SOLVED with a two-tier rule + wordfreq (no gazetteer, UNIVERSAL
  across all 11 languages): Tier 1 dictionary decides spelling (misspelling 'thier' loses to 'their');
  Tier 2 web-frequency separates a lone real name from mishearings ('Kagiso' beats 'Cogizzo'), and
  DEFERS when 2+ plausible names compete ('Njoroge' vs 'Jorg'). Bench-measured on hard clips:
  proper-nouns 0.45->0.35, no regressions, MEAN vote 0.206 -> brain 0.172 (vs single-Deepgram 0.291).
  Validity signal is already universal (every lang has a lexicon backend). Suite 316 green.
- **Multi-model VALIDATED LIVE (2026-07-02, `bench/live_bench.py` on hard clips):** on real hard audio
  the vote beats single-model Deepgram. WER (lower=better): accent+noise 0.105→**0.0**, crosstalk 0.167→0.167
  (tie — overlap is a diarization problem, not a word-vote), propernouns 0.60→**0.45**. MEAN single 0.291 →
  whole-vote 0.240 → **token-vote 0.206**. Token (Phase B) is best overall; won or tied every clip. Clean TTS
  battery still ties (no disagreement to resolve). Hard clips via `bench/make_hard_battery.py`.
- **Phase A ✅ (2026-07-02):** independent-FAMILY voting (same-base Whisper reads share 1 vote;
  specialized fine-tunes independent) + wav2vec2 wired as 9th witness + on-demand LOCAL_TIER
  (free local models fold in only when cloud lacks a 2-family majority). Suite 273 green.
- **Phase B ✅ (2026-07-02):** token-level (ROVER) `consensus_tokens` over the medoid backbone —
  per-word independent-family majority can rebuild a transcript no single model got right, medoid
  backstop prevents disfluent seams, surfaces `uncertain_spans`; `transcribe()` now returns it. Suite 279 green.
- **Phase C ✅ (2026-07-02):** explicit two-tier slow path — Tier-1 normal always; Tier-2 slow
  escalates on uncertainty for general content (stops on convergence), ALWAYS runs the full
  ladder for legal/medical; `transcribe(domain=...)` returns normal_text + slow_changed. Suite 284 green.
- **Phase D ✅ (2026-07-02):** two-detector language id — `detect_multi` cross-checks Deepgram +
  free local Whisper; agree→route, disagree→`candidates` lists both so caller tries both rosters.
  `route()` returns candidates + detect_agree. Suite 289 green.
- **Phase E ✅ (2026-07-02):** `diarize_best` — single primary diarizer when confident (cheap,
  preserves 95.8%); cross-vote (`diarize_consensus`) only when primary is empty/over-segmented.
  Suite 293 green.
- **Phase F ✅ (2026-07-02):** `coherence_homophones(voters=...)` — 2 gated LLM voters (Qwen+Gemini)
  must AGREE on the same in-candidate pick to flag (cuts false positives); default single-voter
  back-compat; unanimous picks marked higher-confidence. Suite 297 green.
- **Phase G ✅ (2026-07-02):** `runner.transcribe_domain_verified` — legal/medical loop: transcribe
  (normal+slow) -> audit vs domain guide -> if a CRITICAL term flagged, re-read + re-audit up to
  max_rounds (stops when clean or a re-read changes nothing). Suite 301 green.
- **Phase H ✅ (2026-07-02):** wired multi-model consensus into `runner.transcribe` (multi_model=ON):
  Deepgram supplies timestamps+speakers (structural backbone), the consensus vote supplies the WORDS
  (`_redistribute` aligns consensus text onto the utterances); graceful fallback to Deepgram text if
  consensus empty. **End-to-end path is no longer single-model.** Suite 304 green.
- **ALL 8 phases (A–H) DONE.** Multi-model upgrade complete.

## Testing (2026-07-02) — coverage push (Phases 1–4 done)
- **266 tests, 0 failing** across 25 files; **74% line coverage** (`pytest --cov=transcript_truth`, see `.coveragerc`).
- **The whole deterministic core is covered** — the "models propose, code decides" verdict path is pinned:
  `grade` 100%, `metrics` (WER + diar-agreement ruler) 96%, `finish`/`report`/`disambiguate`/`manifest` 100%,
  `engine` 97%, `en_rules` 95%, `coherence` 90%, `config` 89%, `semantic`/`lexicon`/`collocation` ~84-89%,
  `legal`/`medical`/`domains`/language rules ~92%+.
- **Model paths tested with the model STUBBED** (no live keys): `en_rules`, `coherence`, `update`, `worker`,
  `runner`, `check_audio`, `engine`(coherence=True). Pattern: monkeypatch the model, assert the deterministic
  gate rejects invented rewrites.
- **Real audio I/O tested with ffmpeg** (synthesized WAV fixture): `chunking.probe/time_stretch/cut_window/
  split_audio` + graceful no-ffmpeg branches (`test_audio_io.py`).
- **`consensus.py` heart pinned:** `_splice` never-lose-A invariant, roster-agnostic `consensus()` (the fix for
  the "silently single-model" bug), `consensus_vote`/`_majority`, `completeness`, seam merge.
- **Honest exclusions (`.coveragerc`):** `acoustic2.py`/`audio.py`/`ccsl_build.py` omitted (experimental/off-path
  external-model wrappers, multi-GB downloads, no branching logic); external ASR/API bodies in `witness.py`
  marked `# pragma: no cover` at the call site (verified via live integration, not unit tests).
- **Still low (specialized/heavy, optional next):** `profiles/agent.py` 18%, `coherence_ml.py` 24%,
  `umls.py` 42% (network), `medical_data.py` 50% (network) — these need live services or are big standalone
  subsystems; not on the core QA path.
- Run: `python3 -m pytest tests/ -q` (or add `--cov=transcript_truth --cov-report=term-missing`).

## Models
- **Wired in-engine:** local Whisper (`whisper` witness — free, all langs, replaces HF 402), Silero VAD (chunk-at-silence), Kiwi (Korean).
- **Installed, not yet wired:** zeyrek (Turkish morph), Stanza (12 langs).
- **Downloading now (background):** Meta MMS, Meta Seamless (~9GB), CAMeL Tools data. PhoWhisper ✅ done.
- **Plan + per-language specialized models:** see `MODELS.md`.

## ✅ pyannote DONE (2026-06-30)
- Fixed torch/torchaudio→2.11.0 matched; removed broken torchvision (pyannote didn't need it).
- `witness.pyannote_diarize` wired (local, free, embedding-based 3rd diarizer + `.speaker_embeddings` = voice fingerprints); registered in `diarize_long`; `diarize_consensus` default now `("deepgram","pyannote")` (free, no Scribe credits). Tested: 2-speaker clip → 2 speakers, 7s.
- Gates accepted: speaker-diarization-3.1, segmentation-3.0, **speaker-diarization-community-1** (the model pyannote 4.x actually loads; use-case="Meeting note taker").

## Plugin update system (2026-06-30) — "get more" on a cadence
- `config.py` (cadence: **off/hourly/daily/weekly/monthly**, stored `~/.config/transcript-truth/config.json`),
  `manifest.py` (`plugins_manifest.json` = installed plugins + versions), `update.py` (diff vs the source
  repo's manifest → pull newer/new plugins; graceful if unpublished). Mirrors cli-enforcement's
  "re-derive from an external source on sync" idea.
- CLI: `--update`, `--update-check`, `--set-update-frequency=weekly`, `--update-status`, `--domain=medical`.
- **TO ACTIVATE remote updates:** push the repo + `plugins_manifest.json` to GitHub `alexander-sorrell-it/transcript-truth` (the configured source). Until then `--update` degrades with a clear message.

## Accounts / sign-in state
- **HuggingFace: SIGNED IN** on the **alex profile** (Chrome via CDP, port **9224**, user-data-dir `~/.creds-alex`). Used to accept pyannote gates + mint the token.
- **pyannote gates accepted:** `pyannote/speaker-diarization-3.1` AND `pyannote/segmentation-3.0`.

## Keys in `~/Desktop/transcript-truth/.env`
NVIDIA_API_KEY · ELEVENLABS_API_KEY (new, fresh credits) · ELEVENLABS_API_KEY_OLD (depleted) ·
DEEPGRAM_API_KEY · GEMINI_API_KEY · HF_API_KEY (inference, depleted/402) · **HF_TOKEN** (read, for model downloads/pyannote).

## Still needs the user
- **NVIDIA Parakeet/Canary:** choose local NeMo vs the build.nvidia.com API.
- (HuggingFace is fully handled — gates accepted, token in place.)

## UMLS (medical terminology) — LIVE (key verified 2026-07-03)
- **`UMLS_API_KEY` is in `.env` and VERIFIED LIVE**: resolves aspirin (C0004057) and multilingually
  diabète/corazon/Herz (FR/ES/DE -> real concepts; ES+DE both -> C0018787 Heart = cross-language norm).
  `umls.py` (umls_term_check) is wired to it. Medical is a single FIELD plugin composing on ANY language
  (UMLS is itself multilingual) -> nothing left to download for medical. Legal remains English-only / hard.

## UMLS — original pending note (SUPERSEDED by the LIVE note above)
- License request SUBMITTED via UTS (account: Alexander-Sorrell-IT, Google sign-in, "Individual Use" /
  "Software development", selected UMLS + RxNorm). NLM reviews in **~3 business days** (may run to ~Jul 6
  due to July 4) → approval email → API key in the UTS Profile.
- WHEN THE KEY ARRIVES: user pastes the UMLS API key → wire a `umls_term_check` that VERIFIES uncertain
  medical terms via the UTS REST API (uts-ws.nlm.nih.gov) — **API lookup, NOT bundled offline** (the UMLS
  license restricts redistributing SNOMED/CPT content, unlike the public-domain RxNorm list we ship).
- Until then, medical coverage is already live: RxNorm drug-name check + ISMP dangerous-abbrev + dosage.
