# Model Map — which models run at which stage (and where we're wrongly single-model)

Source of truth for the multi-model architecture. Rule of thumb: **every stage that makes a
judgment should have ≥2 INDEPENDENT witnesses.** Independence is about *specialization*, not
just brand — see the family rule below.

## The family/specialization rule (how we count votes)

Two models only make a *correlated* error (and so should share one vote) when they are the
**same base weights**. A model is an INDEPENDENT witness if it is a different family **or** a
specialized fine-tune that "hears" differently:

- `hf` (Whisper-large-v3) and injected local `whisper` (faster-whisper) = **same base → 1 vote**, dedup.
- `PhoWhisper` (Vietnamese-specialized Whisper) = Whisper base BUT fine-tuned → **counts as independent.**
- `wav2vec2-XLSR` per-language fine-tunes (e.g. `*-japanese`) = specialized → **independent.**
- Applies to ALL families: a domain/language-specialized variant is a real second opinion even
  if its base family already votes.

Down-weighting only collapses TRUE duplicates (identical base, no specialization).

## Pipeline — models per stage

```
                     ┌─────────────────────────────────────────────────────────────┐
 audio ─▶ STAGE 0    │ LANGUAGE DETECT        now: Deepgram only          ◀ SINGLE  │  → gap
                     │                         →  add Whisper lang-id vote; agree or widen
                     └─────────────────────────────────────────────────────────────┘
                                   │  lang → route to that language's roster + profile
                                   ▼
        ┌───────────────────────────────────────────────────────────────────────────────┐
 STAGE 1│ TRANSCRIPTION WITNESSES (roster)      now: 4 / lang        ◀ MULTI, too narrow  │
        │   NORMAL PASS ─ run the roster concurrently                                     │
        │   independent families available:                                              │
        │     • Deepgram      (proprietary)          • Meta MMS        (CTC/wav2vec2)     │
        │     • ElevenLabs Scribe (proprietary)      • Meta Seamless   (own family)       │
        │     • Gemini        (multimodal LLM)       • wav2vec2-XLSR   (CTC, specialized) │
        │     • Whisper-v3 ┐  same base = 1 vote     • PhoWhisper/etc  (specialized ✓)    │
        │     • local Whisper┘  (dedup)                                                   │
        │   TARGET: 7+ independent votes for well-supported langs (en/es/ja/…)            │
        └───────────────────────────────────────────────────────────────────────────────┘
                                   │  reads {model: text}
                                   ▼
        ┌───────────────────────────────────────────────────────────────────────────────┐
 STAGE 2│ TWO-TIER SLOW PATH  (your spec: normal ALWAYS → slow → COMPARE)                 │
        │   1. score agreement on the NORMAL reads                                        │
        │   2. re-run the roster on PITCH-PRESERVED slowed audio (0.65×, 0.5×)            │
        │   3. fold slow reads into the vote; COMPARE normal vs slow                      │
        │   general content: slow only when normal is uncertain (cost guard)             │
        │   legal/medical:   ALWAYS run slow (see Stage 4 loop)                           │
        └───────────────────────────────────────────────────────────────────────────────┘
                                   │  consensus text  (token-level vote — see below)
                                   ▼
        ┌───────────────────────────────────────────────────────────────────────────────┐
 STAGE 3│ DIARIZATION (who spoke)   now: 1 whole-file diarizer (scribe)  ◀ SINGLE, 95.8% │  → gap
        │   →  cross-vote 2–3 diarizers (deepgram + pyannote + scribe) = diarize_consensus│
        │   words from Stage 2 · speakers from here · merged by timestamp                 │
        └───────────────────────────────────────────────────────────────────────────────┘
                                   │  draft transcript (text + timestamps + speakers)
                                   ▼
        ┌───────────────────────────────────────────────────────────────────────────────┐
 STAGE 4│ QA — DETERMINISTIC, NO MODEL IN THE VERDICT (the thesis — keep single-source)  │
        │   language scanners + optional field layer (legal / medical) + site format     │
        │   coherence witness (homophone pick):  now Qwen only  ◀ SINGLE → add 2nd LLM    │  → gap
        │                                                                                 │
        │   LEGAL / MEDICAL RE-EXAMINATION LOOP (your spec):                              │
        │     a. transcribe normal + slow → consensus text                                │
        │     b. run the legal/medical guide scanners  (COMPARE output to the guide)      │
        │     c. if a critical term is flagged/uncertain (drug name, legal term):         │
        │           re-do normal + slow on THOSE spans, re-compare                        │
        │     d. loop until stable (max 2 rounds) — because legal/medical is high-stakes  │
        └───────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                       receipt (grade + line-cited flags + surfaced uncertainty spans)
```

## Where we're wrongly single-model (the fixes)

| Stage | Today | Fix |
|---|---|---|
| 0 Language detect | Deepgram only | 2-model agree (Deepgram + local Whisper lang-id); disagree → try both rosters |
| 1 Transcription | 4 / lang | widen to **7+ independent** using free local models; dedup same-base Whisper |
| 2 Slow path | escalate on uncertainty | keep for general; **always-on for legal/medical** |
| 3 Diarization | 1 diarizer | cross-vote 2–3 (`diarize_consensus`) |
| 4 Coherence pick | Qwen only | add a 2nd gated LLM (Gemini) voter |
| 4 Verdict/grade | deterministic | **keep single-source, no model — by design** |

## Token-level voting (the proper-noun frontier)

Whole-transcript majority only fires when 2+ reads are byte-identical (common on clean audio,
rare on hard). Adding **per-word (ROVER-style) voting** recovers cases where most models agree on
a word but the medoid model missed it (the "Eleanor→Elena" class). Tradeoff: per-word voting can
stitch a locally-correct but slightly disfluent seam, so we keep medoid as the coherence backstop
and only override a word when a strong independent majority disagrees.

## Open questions (need your call)

1. **Roster size vs his 16GB Air:** the extra witnesses (MMS, Seamless, wav2vec2, local Whisper)
   are free but run locally and are slow on the Air. Always-on for major languages, or only when
   the cloud reads disagree?
2. **Legal/medical loop depth:** 2 rounds max, or keep looping until zero critical-term
   uncertainty (could be slow/expensive on a bad clip)?
3. **Diarization cost:** cross-voting 2–3 diarizers spends more Scribe/Deepgram credits per file.
   Worth it above the current 95.8%, or only when the single diarizer looks unsure?
