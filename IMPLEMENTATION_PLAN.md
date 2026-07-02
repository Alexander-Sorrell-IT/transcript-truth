# Implementation Plan — multi-model upgrades (from MODEL_MAP.md)

Adopted defaults (changeable): local witnesses **on-demand when cloud reads disagree** (protects
the 16GB Air), legal/medical loop **2 rounds max**, diarization cross-vote **only when the single
diarizer looks unsure**. Every phase ships with unit tests and keeps the suite green
(currently 266 passing). Phases are ordered low-risk → high; each is independently shippable.

---

## Phase A — Widen the roster to 7+ independent witnesses  (Stage 1)
**Goal:** more votes, but *independent* ones (family/specialization rule).
- `consensus.py`: add `FAMILY = {model: family}` (whisper / ctc / proprietary / multimodal-llm),
  marking specialized fine-tunes as their OWN family (phowhisper, wav2vec2-xlsr).
- Add local witnesses to major-lang rosters as an **on-demand tier** (run only if cloud reads
  disagree): `mms`, `seamless`, local `whisper`, and wire `acoustic2.read` (wav2vec2) into
  `_witness_call` (the un-hooked 9th model).
- `_majority` / `consensus_vote`: collapse same-`FAMILY` duplicates to **one vote** before counting,
  so 7 witnesses = 7 independent opinions (HF Whisper + local Whisper never double-count).
- **Tests:** family-dedup vote math (pure, stubbed reads); on-demand tier fires only on disagreement.
**Risk:** low (additive). **Payoff:** the "7+ models" ask, done right.

## Phase B — Token-level (ROVER) voting with medoid backstop  (Stage 1 correctness)
**Goal:** recover the proper-noun frontier without Franken-transcripts.
- New `consensus_tokens(reads)`: align reads, take per-word majority, but **override a word only
  when a strong independent (cross-family) majority disagrees** with the medoid; else keep medoid's word.
- Return `{text, uncertain_spans}` — the surfaced-uncertainty map (feeds the receipt).
- **Tests:** majority word wins; single outlier can't flip; disfluent-seam guard; spans reported.
**Risk:** medium (changes chosen text). **Payoff:** fixes the one measured WER weakness.

## Phase C — Explicit two-tier slow path  (Stage 2)
**Goal:** your normal → slow → compare, wired predictably.
- Refactor `transcribe()`: always score normal; general content escalates to slow on uncertainty;
  **legal/medical always runs slow**. Return `normal_text`, `slow_text`, and their diff.
- **Tests:** general skips slow when confident; legal/medical always slows (stubbed roster).
**Risk:** low. **Payoff:** predictable, documented behavior.

## Phase D — Multi-model language detect  (Stage 0)
**Goal:** stop a single detector mis-routing the whole job.
- `language.detect()`: Deepgram detector **+** local Whisper lang-id; agree → route; disagree →
  return both candidates and let the caller try both rosters (or pick by first-pass agreement).
- **Tests:** agree path; disagree returns both (stubbed).
**Risk:** low. **Payoff:** removes a cascading single point of failure.

## Phase E — Diarization cross-vote when unsure  (Stage 3)
**Goal:** raise the speaker-ID floor on hard files.
- `diarize_long()`: if the single whole-file diarizer fails or looks unsure (e.g. speaker count
  unstable), fall to `diarize_consensus` (deepgram + pyannote + scribe cross-vote).
- **Tests:** confident single path unchanged; unsure path invokes consensus (stubbed diarizers).
**Risk:** low-med. **Payoff:** protects the 95.8% on the tail.

## Phase F — Second coherence LLM voter  (Stage 4)
**Goal:** two gated opinions on homophone picks, still no model in the verdict.
- Coherence pick: `Qwen` **+** `Gemini`, both deterministically gated (closed candidate list);
  flag only when they agree, else surface as review.
- **Tests:** agree → flag; disagree → review; neither can invent a non-candidate (stubbed).
**Risk:** low. **Payoff:** fewer missed/false homophone flags.

## Phase G — Legal/medical re-examination loop  (Stage 4)
**Goal:** the high-stakes double-check you specified.
- New runner path for `domain in (legal, medical)`: transcribe normal+slow → run the domain guide
  scanners → if a critical term (drug name / legal term) is flagged or uncertain, **re-read those
  spans normal+slow** and re-compare → loop **max 2 rounds** → surface anything still uncertain.
- **Tests:** clean transcript stops at round 1; a seeded uncertain drug name triggers a re-read
  and resolves or surfaces (stubbed roster + real scanners).
**Risk:** medium. **Payoff:** the safety margin where errors are worst.

## Phase H — Wire the multi-model engine into `runner`  (the headline)
**Goal:** the end-to-end path stops being single-model Deepgram.
- `runner.transcribe()`: use **consensus text** (Stages 1–2) merged onto **Deepgram structure**
  (timestamps + speakers from Stage 3) — text from the vote, timing/speakers from the backbone.
- Do this **last**, once the improved consensus (A–C) is proven, so we wire in the good version.
- **Tests:** end-to-end wire with stubbed witnesses — multi-model text, Deepgram timestamps kept.
**Risk:** high (engine heart). **Payoff:** closes the #1 gap — "never one model" actually holds.

---

## Sequencing & checkpoints
A → B → C build the better consensus in isolation (safe).
D, E, F are independent single-model→multi fixes (any order).
G depends on C. **H depends on A–C and is the final wire-in.**
Checkpoint after each phase: full suite green + a short note in `SESSION_STATE.md`.
No phase deletes the deterministic verdict path — that stays single-source by design.
