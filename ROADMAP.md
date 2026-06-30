# transcript-truth — Build Plan

A step-by-step roadmap for everything requested: long-audio multi-model consensus,
measurement, adversarial gap-finding, language expansion, auto-detect + routing,
code-switching, and translation. Sequenced by dependency — earlier phases unblock later ones.

## Full feature checklist (status as of this session)
Legend: ✅ done · 🟡 partial/proven-but-not-wired · ⬜ planned · ⭐ pre-existing (his design)

- ⭐ Multi-model consensus core (models propose, deterministic verdict)
- ⭐ Plug-in per-language profile architecture
- ⭐ No-model-in-the-verdict-path spine
- ✅ Long-audio chunking for all witnesses (overlap + fuzzy stitch, `bad_seams=0`)
- ✅ Roster-agnostic `consensus()` (strongest non-empty reads, not hardcoded)
- ✅ Robust whole-file diarization (transport retry) — Scribe full file = 3 consistent speakers
- ✅ HF retry (cold-start/throttle hygiene)
- ✅ Cross-diarizer speaker consensus — wired in-engine (`consensus.diarize_consensus` + `speaker_consensus.cross_consensus`); agree=confident, split=flagged-for-review; graceful witness drop. Measured 63.3% Deepgram↔Scribe on the crosstalk test (honest uncertainty signal, not a quality score)
- 🟡 Per-language rosters — exist for ja/en/es/ru/uk only
- ⬜ Chunked diarization with correct speaker IDs — **rolling carry-over** (default) + **reference-map** (robust)
- ⬜ Voice-fingerprint (embedding) backstop for huge files
- ✅ Measurement: number-aware WER + diarization-agreement scorer (`metrics.py`) + 6-case TTS battery w/ exact ground truth (`bench/`) + baseline scorecard (`bench/BASELINE.md`); reads saved for re-scoring without API
- 🟡 90-95% honest-uncertainty policy — operationalized (consensus agreement % + surfaced-uncertainty reported); not yet a hard gate. Baseline confirms it: 0.0 WER clean / 94.4% proper-nouns / 100% seq / 90% crosstalk diarization
- ✅ Language auto-detect → route to roster/profile (`language.detect`/`route`/`profile_for`, `runner.transcribe_auto`); detects on a slice, graceful fallback to `default` for unbuilt languages; verified en+ja live
- ⬜ Code-switching (2 speakers, 2 languages) — per-turn language-ID
- 🟡 New languages: **fr, de, pt, tr, ko, vi ✅** (validated live) · **ar, hi, ur 🟡** (profiles+rules+routing done & tested; witness ASR quality not yet battery-validated) · not Chinese
- ⬜ Specialized witness models per hard language
- ⬜ Adversarial gap-finding agents (worst-case battery)
- ⬜ Translation (EN→X) with mechanical QA + surface-for-review faithfulness

## Architecture: TWO orthogonal axes — language × domain
A transcript is audited with a **language** plugin (en/fr/ja… — lexicon + language rules + roster)
AND an optional **domain** plugin (medical/legal/… — language-agnostic rules). They COMPOSE:
`audit_transcript(text, profile="en", domain="medical")` runs both scanner sets. So any domain works
with any language. `domains.py` = the domain registry + `compose()`.
- ✅ **Domain axis built** — `domains.py`; **medical** domain done (`medical_rules`: ISMP "Do Not Use"
  dangerous-abbreviation list + dosage hygiene — a safety crown jewel; composes across languages, tested).
- ✅ **legal** migrated onto the domain axis — `domains.py` registers `legal` (structural CVL: titles,
  numbers, a.m./p.m., tags, non-verbals, spacing) composing with ALL languages; the English-specific
  CVL half (spelling/slang/grammar) stays in the full `legal` profile. Per-language legal style data
  (e.g. French/German legal conventions) is the "more resources" path, like language lexicons.
- ⬜ Add more domains (financial, etc.); per-language legal data; optional auto-pick domain by keyword.

## Cross-cutting principles (apply to every phase)
- **No model in the verdict path.** Deterministic scanners own the grade; models only propose.
- **Surface uncertainty, never hide it.** Target max accuracy + honest flags → believable high-90s, not a fake 100%.
- **A language profile = 4 parts:** roster (which witness models) + tokenizer + deterministic rules + optional `:full` coherence layer.
- **Every new capability ships with tests + a battery scenario.** Nothing is "done" until it's measured.

---

## Phase 0 — Finish & harden the long-audio core  ✅ COMPLETE (2026-06-30)
**Goal:** the multi-model long-audio path is complete and in-engine, no one-off scripts.
**Done:** chunking + fuzzy stitch (bad_seams=0); roster-agnostic consensus; robust whole-file
diarization (retry); reference-map diarization (95.8%); cross-diarizer consensus
(`diarize_consensus`/`cross_consensus`, graceful witness drop); measurement ruler (`metrics.py`);
21 tests passing (9 new). Open follow-ups (quality, not blocking): add Gemini as a 3rd tie-break
diarizer; resolve (not just flag) disagreement turns via a 3rd diarizer/embeddings.
1. Chunk `elevenlabs_diarize` (it SSL-failed on the full 13MB upload) — same overlap-chunk path as the reads, rebasing turn timestamps by chunk offset.
2. Wire cross-diarizer **speaker consensus** (Deepgram + Gemini + Scribe) into the engine pipeline (fold `run_consensus.py` logic into `speaker_consensus`/a runner; delete the one-off).
3. Graceful witness degradation: skip out-of-credit/4xx witnesses, log which dropped and why (no silent empties).
4. **Verify:** one clean run on the Ubiqus audio → 3-diarizer consensus, `bad_seams=0`, agreement reported.

## Phase 1 — Measurement foundation (ground truth)  ✅ CORE COMPLETE (2026-06-30)
**Goal:** turn "plausibly better" into a number.
**Done:** number-aware WER + diarization-agreement scorer (`metrics.py`); 6-case TTS battery with
exact ground truth (`bench/make_battery.py` → clean/numbers/fast/noisy/2-spk-seq/2-spk-crosstalk);
baseline scorecard (`bench/run_baseline.py` → `BASELINE.md`, reads saved for re-scoring). Baseline:
WER 0.0 clean/fast/noisy/2-spk, 0.056 proper-nouns; diar 100% seq / 90% crosstalk.
**Follow-up (grow over time):** add REAL hard clips (accents, real crosstalk, code-switch) with
reference transcripts — TTS battery is a clean upper bound. Make 90-95 a hard pass/fail gate.
1. Curate a **worst-case battery** with reference transcripts: clean single-speaker, crosstalk, heavy accents, fast speech, low SNR, proper nouns/numbers, long silence/music, code-switching.
2. Metrics harness: **WER** (text), **DER / speaker-error** (diarization), per-scenario breakdown.
3. **Baseline** the current engine on the battery → the number every later phase improves against.
4. Operationalize the 90-95 rule: report accuracy *and* the count/locations of surfaced-uncertain spans.

## Phase 2 — Language auto-detect + routing  ✅ COMPLETE (2026-06-30)
**Goal:** point the engine at audio, it picks the right language stack itself.
**Done:** `witness.deepgram_detect_language`; `language.detect` (slice-based, cheap) / `route` /
`profile_for` / `script_of` (multilingual script classifier — the per-turn-tagging hook);
`runner.transcribe_auto` (detect→route→transcribe, graceful fallback to `default` for unbuilt
languages); added `ja` to the roster. Verified en+ja detect/route live; 25 tests pass.
**Open follow-up:** per-turn tagging is script-based (splits ja/en/cyr/ko/ar/hi) but can't split
SAME-script languages (es↔en, ru↔uk, de/fr/pt) — that needs a langid model (Phase 6 code-switching).
1. Front-end **language-ID** pass (Whisper/Gemini/Deepgram all return detected language; pick by vote).
2. **Router:** detected language → that language's roster + profile.
3. Extend `language.py`/`segments()` for **per-turn language tagging** (the hook code-switching needs later).
4. **Verify:** mono-lingual files in ja/en/es/ru/uk route correctly with no manual `--profile`.

## Phase 3 — Tier-1 languages (Latin script, near-free)  ✅ COMPLETE (2026-06-30)
**Goal:** German, French, Portuguese, Turkish — cheap, high-quality with the current roster.
For each: validate the 4-witness roster stays in-language → write `xx_rules.py` (spacing, punctuation, language-specific mechanical checks, reusing the `es`/`ru` pattern) → register `xx` profile → add to `consensus.ROSTER` → tests + a battery scenario.
**All four done** — each = `profiles/xx.py` (shared lexicon authority check + a deterministic crown-jewel rule) + `consensus.ROSTER` entry + tests; auto-route via Phase 2.
- **fr** — `fr_rules.french_spacing` (space before ; : ! ? » / after «; ignores times). Validated live (Scribe WER 0.0).
- **de** — `de_rules.german_old_spelling` (pre-1996 ß: daß→dass …). Validated live (de audio→de route).
- **pt** — `pt_rules.portuguese_cedilla` (ç before e/i is always wrong; ç+a/o/u ok).
- **tr** — `tr_rules.turkish_foreign_letters` (q/w/x not in the Turkish alphabet; lexicon degrades to wordfreq since pyspellchecker lacks tr).
Note: number-aware WER is English-only; non-English number normalization is a metric follow-up.

## Phase 4 — Tier-2 languages (script/structure quirks)  ✅ COMPLETE (2026-06-30)
**Goal:** Korean, Vietnamese.
- **Korean ✅** — `ko_rules.korean_particles`: batchim particle check (은/는·이/가·을/를·과/와·(으)로) — Unicode arithmetic owns the verdict, **Kiwi** (`kiwipiepy`, installed) only locates particles so real words (마을/차이) don't false-fire. Surface-split + Kiwi guards → catches the common errors with **zero false positives**; safe miss when Kiwi reads the error as a valid word (책가). `ko`+`ko:full` registered, in ROSTER, validated live (ko audio→ko route). Honest gaps: no lexicon check (Korean wordfreq needs mecab_ko_dic); 띄어쓰기 spacing + Sino-Korean homophones = ko:full TODO.
- **Vietnamese ✅** — `vi_rules.vietnamese_foreign_letters` (f/j/w/z absent from the Vietnamese alphabet) + wordfreq lexicon (pyspellchecker lacks vi → degrades to frequency; the Latin regex handles ư/ơ/đ diacritics). `vi`+`vi:full` registered, in ROSTER, validated live (vi audio→vi route).

## Phase 5 — Tier-3 hard languages (specialized models)  🟡 PROFILES DONE (2026-06-30); witness eval pending
**Goal:** Arabic, Hindi, Urdu.
**Done:** `ar`/`hi`/`ur` (+`:full`) profiles — lexicon (ar via pyspellchecker; hi/ur via wordfreq) +
`script_rules` (tatweel removal for ar/ur, Latin-leak for all) + ROSTER + routing + tests. **Still open
(the real Phase-5 work):** evaluate witness ASR *quality* per language and swap in specialized models
where the general roster is weak — needs $ + per-language reference clips. See model-strategy notes.
1. Evaluate witness quality per language; **acquire specialized models** where the general roster is weak (NVIDIA NIM, language-specific Whisper variants, etc.).
2. Per-language **model profile** = the best witnesses for that language (like the `uk` roster that excludes drifters).
3. Script handling: Arabic RTL + omitted diacritics + dialect; Hindi/Urdu (spoken-similar, written-different).
*(Chinese deliberately excluded — tonal + character homophones = Japanese-hard ×2.)*

## Phase 6 — Code-switching / multilingual audio
**Goal:** 2 speakers in 2 languages, handled correctly.
Diarize → **per-turn language-ID** (Phase 2 hook) → route each turn to its language profile → merge. Build on Phase 2 routing + diarization.

## Phase 7 — Adversarial gap-finding agents
**Goal:** hunt every worst case, make it bulletproof.
Multi-agent harness: each agent probes one failure mode against the Phase-1 battery, finds gaps, reports; loop-until-dry. Gaps → prioritized fixes back into profiles/rosters. *(Multi-agent = real token cost; run with explicit opt-in.)*

## Phase 8 — Translation (EN → X)  *(parallel track)*
**Goal:** the inverse — translation, with the same verdict philosophy.
1. **Translation-QA profile** = mechanical deterministic checks: numbers/names preserved, no untranslated segments, terminology-glossary adherence, length sanity.
2. Per-language translation profile.
3. Semantic faithfulness = **surface-for-review** (model proposes, bilingual/human verifies) — never in the verdict path.

---

## Suggested order & rationale
**0 → 1 → 2 → 3 → (4, 8 in parallel) → 5 → 6 → 7.**
Measurement (1) before any language work so every addition is provable. Routing (2) before languages so they auto-activate. Tier-1 (3) first for fast wins. Adversarial agents (7) last, once there's a battery + multiple languages to stress.
