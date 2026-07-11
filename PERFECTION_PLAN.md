# Path to "perfect" — measured, phase by phase

**Definition of perfect (achievable, testable):** the consensus is the best transcriber available
in every language — it beats any single model — proven on real hard audio, with every data cell full.
(Literal 0.0 WER isn't the target; pro human inter-transcriber agreement is ~92–96%.)

Every phase ships with unit tests AND a bench measurement. A phase is DONE only when the number moves
the right way (or is proven neutral). Baseline to beat (English hard clips, WER, lower better):
single-Deepgram 0.291 · whole-vote 0.240 · token-brain 0.172 · **best single model (Scribe) 0.150**.

**Operating principle (proven 2026-07-07, 4-for-4):** every "impossible" so far was an unfound bug
(broken Arabic ruler, unintelligible Urdu TTS, missing reliability row, CER-vs-WER unit mismatch).
Don't call ceilings — find the next bug. And measure EVERYTHING: 10 rule ideas tested that day,
3 shipped, 7 rejected by the numbers.

## Phase I — Reliability weighting ✅ DONE (2026-07-03) — consensus BEATS best single model
Unweighted votes let a mediocre crowd outvote a proven-strong model. Add per-witness reliability:
steer the UNCERTAIN positions (judge deferred, no family majority) to the most-reliable witness
instead of the medoid; weight family votes by reliability. Surgical — must not regress the clips
the consensus already wins (accent_noise 0.0).
- **DONE:** consensus 0.050 < Scribe 0.068 < single-Deepgram 0.291. accent_noise 0.0 (beats Scribe),
  crosstalk 0.0, propernouns 0.15. Mechanism: reliability-anchored backbone (`_anchor_name`: start from
  the most-accurate witness, refine word-by-word) + prune-garbage-then-reliability word decision
  (`_decide_word`). Note: RELIABILITY priors are English-bench-derived (global) — Phase II calibrates per language.

## Phase II — Measure every language ✅ DONE (2026-07-07) — one ruler, 13 languages
- `metrics.cer` = the cross-language ruler (space-free per-char, same normalization as wer);
  the old table compared ja/ko CER to word-WER elsewhere — unit artifact, ja is mid-pack.
- Arabic ruler fixed (diacritics/hamza/ordinals/case-inflected numbers were scored as errors).
- Urdu measured for the first time (edge-tts neural battery; espeak was unintelligible). Scribe
  emits DEVANAGARI for Urdu (right words, wrong script) → ur reliability scribe=0.0.
- Vote hardened, each measured: annotation strip, wrong-script veto, Devanagari fold.
- Medical ISMP dangerous-abbreviations promoted to UNIVERSAL domain core (all 13 languages,
  0 FPs on 91 multilingual clips; short abbrevs need dose context outside en — 'u'=tumor in vi).
- **One-ruler map (consensus CER):** ko .017 · fr .031 · pt .032 · uk .034 · de .039 · ru .043 ·
  ja .044 · es .045 ‖ ar .076 · tr .081 · hi .084 · ur .097 · vi .102
- **Measured-and-REJECTED (don't retry without new data):** anchor reweighting ×3,
  majority-overrides-valid-backbone ×2, gazetteer-name preference ×2, char-level name
  reconstruction (recovers Kowalski-class garbles in PoC; fires 0 in-engine at damage-safe
  thresholds — junk gazetteer surfaces are the blocker), Turkish specialist witnesses
  (300M XLSR 0.623 solo; whisper-turbo-finetune 0.380 solo AND zero vote effect).

## Phase III — TASK-ROUTED MODELS (⬅ CURRENT — "the right model for each job")
CORRECTION (2026-07-08, he called it): the verdict layer is NOT "at peak" — that claim was
disproven one commit later when the re-ask loop (a new DETERMINISTIC stage) beat it. The accurate
statement: WORD-VOTE RULE TWEAKS can no longer be verified on 91 TTS clips (the noise floor eats
±3-case changes). Deterministic headroom that remains — verifiable once Phase IV's big battery
exists — lives in Phase VII below. Meanwhile the cheapest verified gains are in HOW models are used.
Principle applied recursively: generic ears find the questions, specialist attention answers them,
code grades the answers. Verdict stays deterministic — untouchable. The role map:
first-pass = per-language measured roster (done) · diarization = Deepgram+Scribe cross-vote (done) ·
contested spans = focused re-ask (III.1) · proper nouns = primed propose + gazetteer verify (III.2) ·
numbers/dosage/format/verdict = pure code, never a model (done, locked).

### III.1 Contested-span re-ask loop ✅ SHIPPED (2026-07-07, live-measured)
Cut just the uncertain-span seconds; two fresh independent ears must agree; adoption guards
(plausible / never-downgrade-known-name / no-fragment) each exist because their absence measurably
failed. tr/ar/ur hard clips: 0.238 -> 0.231 WER, 0 regressions ('White' -> 'Bay'). TIER 3 in
consensus.transcribe. Gemini free tier 429s often — fallback chain covers it; a paid key steadies it.

#### Original spec
The engine already knows its uncertain spans. New stage: cut those seconds of audio (word
timestamps exist from Deepgram/Scribe), re-send ONLY that slice to (a) the strongest witness for
the language and (b) context-primed Gemini ("candidates: 'Kowalski/Kohauski'; Polish surname
context"). Re-vote on the span with the fresh reads added. Cost: pennies, targeted exactly where
the errors are. **Done when:** bench WER drops on contested spans with zero regression elsewhere,
and the flagged-for-review count falls.

### III.2 Primed second reads (domain/context-aware proposing)
When domain=medical/legal, Gemini's prompt carries the domain vocabulary; when a first pass
surfaces candidate names, the re-read receives them as candidates. Models propose better; code
still decides. **Done when:** proper-noun WER (the measured frontier in every language) improves
on the fp_* battery.

### III.3 Witness audition harness ✅ SHIPPED (2026-07-07)
`bench/audition_witness.py <model> <lang>` — battery WER vs roster, ROSTER-WORTHY/VOTE-FODDER/REJECT,
refuses to --commit a REJECT. Family-dedup enforcement still TODO (roster slots holding same-base
duplicates: hf + local whisper).

#### Original spec
`bench/audition_witness.py <model-ref> <lang>`: runs the battery, prints WER vs current roster,
writes the reliability row ONLY if it wins, auto-registers family. Turns a session of specialist
hunting into 10 minutes. Also enforces: roster slots require DISTINCT families (hf + local
whisper are the same base = one vote pretending to be two — free the slot).
**Done when:** adding/rejecting a candidate witness is one command with a measured verdict.

### III.4 Trailing-language witness hunt (use III.3)
ar/tr/hi/ur/vi trail because commercial ASR under-trained on them (correlated garbles the vote
can't fix). Audition: Deepgram language-boost modes, Gemini prompt-steered transcription,
AssemblyAI/Speechmatics per-language, bigger community fine-tunes. Keep only measured winners.
**Done when:** each trailing language has ≥3 genuinely independent families, or documented
that none better exist (that's data, not failure).

## Phase IV — Real audio (unblocks all remaining tuning)
FLEURS has real human speech + verified transcripts in all 13 languages, free. 91 TTS clips is
too small to tune knife-edge rules (every borderline change flips 3, breaks 3) and TTS voices
mangle the foreign names the models get blamed for. Pull ~50 clips/lang, re-run the map.
Also: quality-filter the gazetteer (frequency floor) — junk surname surfaces are what killed
name reconstruction; with clean data + real audio, re-audition that stage (code is in git history).
Subsumes old Phase III data cells (Leipzig collocations, Wikidata gazetteer upgrade).
**Done when:** the parity map is re-measured on real speech and thresholds are re-tuned on it.

## Phase V — Hard uncertainty gate (policy → guarantee)
Below-threshold consensus agreement must REFUSE to ship (return flagged-for-review status), not
just report a number. Turns the 90–95% honest-uncertainty philosophy into a mechanical guarantee.
**Done when:** a low-agreement transcript cannot exit the engine ungated, pinned by test.

## Phase VI — Legal multilingual + registration scaffold
- Move the English CVL content half onto the legal domain axis where portable; IATE for EU
  languages. Honest ceiling — global legal isn't a data download.
- `new_language.py` / `new_site.py` scaffolds that REFUSE to register without a battery score
  (Urdu sat wired-but-unvalidated for a week; make the plugin system self-enforcing).

## Phase VII — Determinism headroom (NOT peaked; verifiable only after Phase IV's battery)
Concrete deterministic mechanisms NOT yet built — parked because the 91-clip battery can't
verify ±3-case changes, not because the ideas are exhausted:
- **Adjudicator confidence dial**: _ADJ_STRONG=1.0 is maximally conservative; the collocation/
  validity judge overrides the vote only on a full-point margin. Sweep it on the big battery.
- **Phonetic-distance voting**: word candidates scored by SOUND distance (metaphone/epitran
  per-language), not surface edit distance — 'Kohauski/Kowalski' are phonetically near-identical,
  'kadınsı/Kagiso' aren't. Fixes the name knife-edges the surface vote can't split.
- **Cross-file name consistency**: the same speaker's name must resolve to ONE spelling across
  the whole transcript — a second appearance of 'Kowalski' heard clean should overwrite the
  first appearance's garble. Pure code, zero API.
- **Clean gazetteer**: frequency-floored name list (junk surname surfaces killed name
  reconstruction twice AND poisoned the reask downgrade guard — 'White' blocked as a "name").
  Then re-audition char-level name reconstruction (code in git history, PoC recovered
  Kowalski/Kagiso/Ljubljana).
- **Number cross-check stage**: digits are the highest-stakes tokens; a dedicated numeric-
  agreement pass (all witnesses' numbers canonicalized and diffed) with mandatory flag on any
  disagreement — cheap, deterministic, catches the '12 thousand' vs '2 thousand' class.
- **Punctuation/casing consensus**: currently backbone-inherited; vendors grade on it (DT test
  feedback was 'missing/incorrect dialogue' — formatting counts). Vote it like words.

---

# THE FINISH PLAN (2026-07-11) — from here to test-day, checklist form

Phase IV landed its first result and REWROTE the target list: on REAL speech (FLEURS) ar=99.3%,
tr=98.5%, vi=97.1%, ur=95.5% char-accurate — the "trailing five" were mostly a torture-test
artifact. The genuine remaining problems are NARROW: hi (91.7%), ja (92.7% — real speech is
harder for it than TTS), and Urdu word-segmentation (WER .189 vs CER .045 = boundaries, not ears).

## Session A — close the engine work
- [ ] **A1. Finish the real map** (rest of Phase IV): pull + bench fr/de/pt/ru/uk/es/ko real
      clips (`make_real_battery.py 10 fr de pt ru uk es ko` → `live_bench_real.py …`).
      Mostly unattended. Done when: all 13 languages in real_audio.json.
- [ ] **A2. Urdu segmentation fold** (hours, pure code): fold clitic/space variants in the
      ruler + profile so ur WER measures words, not orthographic joining. Done when: ur real
      WER drops toward its CER without the CER moving.
- [ ] **A3. hi + ja witness audition** (harness is one command per candidate):
      hi — ARTPARK vaani-hindi, Oriserve Hindi2Hinglish, Deepgram hi boost;
      ja — diagnose first (read the real-clip reads: conversational style? then audition
      ReazonSpeech/kotoba-whisper). Keep measured winners only.
      Done when: hi/ja real-CER improve or documented no-better-exists.
- [ ] **A4. Phase V hard gate** (half-session): consensus agreement < threshold →
      Receipt refuses to ship (status='review', text withheld from the clean path),
      pinned by test. Done when: a low-agreement transcript cannot exit ungated.

## Session B — armor + the tests
- [ ] **B1. Phase VI legal migration**: portable CVL content (titles/numbers/spacing already
      domain-side) — move the language-neutral remainder; en-specific half stays en. Done when:
      compose('en','legal','transcribeme') carries the full CVL ruleset and tests pin it.
- [ ] **B2. Registration scaffolds**: new_language.py / new_site.py refuse to register without
      a battery score (the Urdu lesson, made mechanical).
- [ ] **B3. Dry run**: one full legal-style audio → engine → transcribeme-format audit → fix
      flags → A-grade receipt. Same for a medical voicemail → quicktate format. TIMED (the DT
      lesson: clock-first, submit solid, verify delivery).
- [ ] **B4. TAKE THE TESTS**: TranscribeMe (legal) + Quicktate AI-Editor-Part-2 path (medical),
      engine-audited before submission, delivery verified early.

## After money (optional polish)
- Phase VII determinism items, verified against the full real battery.
- Phase III.2 primed reads (needs steady Gemini quota — paid key).
- Remaining fp_* torture-test gap-closing (it's the worst-case bound, not the product claim).

The product claim, already banked: **measured on real human speech: 95.5–99.3% character
accuracy (5/7 languages benched so far), every uncertain word flagged, deterministic verdict.**
