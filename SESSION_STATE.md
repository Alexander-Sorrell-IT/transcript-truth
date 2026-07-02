# transcript-truth — session state (2026-06-30)

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
- **Phase A ✅ (2026-07-02):** independent-FAMILY voting (same-base Whisper reads share 1 vote;
  specialized fine-tunes independent) + wav2vec2 wired as 9th witness + on-demand LOCAL_TIER
  (free local models fold in only when cloud lacks a 2-family majority). Suite 273 green.
- Phases B–H pending: token-level voting, two-tier slow path, multi-model detect, diarization
  cross-vote, 2nd coherence LLM, legal/medical re-exam loop, wire consensus into runner (last).

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

## UMLS (medical terminology) — PENDING APPROVAL (requested 2026-06-30)
- License request SUBMITTED via UTS (account: Alexander-Sorrell-IT, Google sign-in, "Individual Use" /
  "Software development", selected UMLS + RxNorm). NLM reviews in **~3 business days** (may run to ~Jul 6
  due to July 4) → approval email → API key in the UTS Profile.
- WHEN THE KEY ARRIVES: user pastes the UMLS API key → wire a `umls_term_check` that VERIFIES uncertain
  medical terms via the UTS REST API (uts-ws.nlm.nih.gov) — **API lookup, NOT bundled offline** (the UMLS
  license restricts redistributing SNOMED/CPT content, unlike the public-domain RxNorm list we ship).
- Until then, medical coverage is already live: RxNorm drug-name check + ISMP dangerous-abbrev + dosage.
