# transcript-truth — Full Status & Findings

_Complete record of what was built, every background process run, what was measured, and the honest conclusions. Written 2026-06-19._

---

## 0. CURRENT STATE — read this first (updated 2026-06-20)

**What this is now:** a working Japanese transcription-QA engine on the RoboTruth principle (model does the work, deterministic checks verify it). NOT "Japanese is impossible" — that handoff was wrong and is retired.

**Architecture: worker + auditor.**
- **Worker** = Qwen via NVIDIA API (`transcript_truth/worker.py`; key in gitignored `.env`, model `qwen/qwen3-next-80b-a3b-instruct`). Does the Japanese (correct/produce). Fallible — rubber-stamps, invents words — so it NEVER gets the final word.
- **Auditor** = deterministic layers in `transcript_truth/`: `verdict.verify()` (audio: claim vs independent ASR read), `engine.audit_transcript()` (text: scanners → graded receipt), `scanners.py`, `kana_rules.py` (rule-24, 12/12 fixtures), `collocation.py` (context tie-break), `coherence.py` (opt-in Qwen blank-fill, gated).

**Measured (honest):**
- Multi-read injection test (audio anchor): **19/20 = 95%** catch on the editing-AI-transcripts error type.
- Text-only (no audio): 60% — the audio anchor is what flattens homophones via context.
- Quiz (GoTranscript JP, 10 MC rule questions): Qwen alone 4/10; **system 6/10 derived-with-certainty** (kana/dictionary/timestamp-math) + fixes Qwen's errors. Quiz needs 100%; retake has a few-day cooldown.
- False-alarm noise: ~0.05 flags/clip on 80 correct clips.

**Design fixes landed this session (2026-06-20):**
1. **Grade now reflects meaning** (`grade.py`): kana violations = `moderate` (move grade), review items cap at B. Was: grade blind to all meaning errors (always A).
2. **Coherence witness WIRED** (`audit_transcript(text, coherence=True)`) — was dead code. Catches 菓子→華氏 thin-context homophones. Opt-in (uses Qwen).
3. **`verify` normalization** — 100/百, particle drops, inserted fillers no longer false-flag MISHEARD.

**Data assets (`data/`):** full JMdict (217k) + common; `jp_name_surfaces.json` (954k names); `jp_collocations.json` (30k wiki articles, 152k words); `jp_reading_index.json` (49k ambiguous readings, freq-sorted — powers coherence); `jp_kanji_readings.json` (10,384 KANJIDIC2, **inert/unwired**); `jp_pitch_accent.json` (118k, distinguishes 橋/箸, **inert/unwired**); `jp_homophones_by_reading.json`; `jp_asr_confusions.json` (**building** — empirical Whisper error pairs from 140 clips); audio: `data/sounds/` (80) + `data/sounds2/` (60), all FLEURS (same domain).

### BILINGUAL CONSENSUS PIPELINE — landed 2026-06-20 (major)

Real audio is bilingual (JP + EN). Built the multi-witness, language-aware pipeline. Core principle (user-driven): **never rely on one model — agreement across independent models IS the verification; one model = no verification.**

- **4 independent witnesses** (`witness.py`, keys in `.env`): **ElevenLabs Scribe** (`scribe_v1`, beats Whisper on JP FLEURS), **Deepgram Nova-3**, local **Whisper medium**, **Gemini** (`gemini_read`, multimodal LLM, model-fallback list — **strongest on bilingual**: clean JP+EN in one pass since it reasons over context, not just acoustics). Keys in gitignored `.env` (Scribe=STT scope, Deepgram=Default role, Gemini=AI Studio `AQ.`-format key). `panel()` runs all 4.
- **`consensus.py`** — `panel(audio)` runs all 3; `consensus(reads)` aligns the 2 strong reads (content tokens only, punctuation stripped), reports **agreement %** (locked) + **disagreement spans** (ear-check); Deepgram breaks ties. On the test clip: **53% content locked, 13 real disagreements — all concentrated in the English** (correctly localized the hard part).
- **Language-aware ACOUSTIC routing** — the key fix: models in JP-mode garble accented English, EN-mode garbles JP. So run **JP-mode read + EN-mode read** (`elevenlabs_read(audio, language='eng')`), then Qwen **stitches**: JP base kept complete, katakana-English spans swapped for the EN-read's clean English. Closed the garbled-English problem (FUM/BAD → "Your English is very good, but—").
- **`language.py`** — `segments()` splits mixed lines into JP/EN runs (script-based, deterministic) → routes JP runs to JP checks, EN runs to EN checks in `audit_transcript(coherence=True)`.
- **`en_rules.py`** (EN homophone catalog, 96 confusable sets, Qwen-proofread + catalog-gated) + **`en_format.py`** (slang→standard, Okay, yeah→yes, abbreviations, brackets, numbers) — the English half of the guideline ruleset, recall-tuned (native reader filters).
- **Two new deterministic safeguards** (catch what the stitch model misses): **`untranslated_english`** scanner (long non-dictionary katakana = English-as-katakana → flag + auto-fix loop using the EN-read; the アイラブディスムービー leak now caught + fixed, 0 remaining) and **`completeness(base, final)`** in consensus (fraction of base JP content kept; <70% = dropped content — closes the auditor's blind spot where a half-empty transcript false-passed as grade A).

- **Deterministic finishing layers** (no model — the safe path after Qwen cleanup proved unstable): `finish.py` `clean_verbatim_finish()` (removes standalone fillers anywhere incl. あの-before-English, fixes English-word + full-width 。/、 → English punctuation), `sound_events.py` `normalize_sounds()` + `sound_event_format` scanner (model `(laughs)`→`[laughs]`; JP vocalizations ふん→[scoffs]/しっ→[shushing]/はぁ→[sighs] → guideline brackets), `mixed_punctuation` scanner in `en_format.py`, short-katakana-English catch in `untranslated_english` (bilingual-gated: オーマイゴッド/ライト flagged only when English on the line, so monolingual loanwords don't false-fire). **Pipeline shape that WORKS:** Gemini read = base → guarded Qwen clean (reject+retry if `completeness`<0.6, i.e. Qwen translated) → deterministic `.replace()` for clear katakana → `clean_verbatim_finish` → `normalize_sounds` → audit. Produced the test-clip Step-2 transcript at **grade A, complete, 0 flags** (cached reads `/tmp/reads4.json`).

**GoTranscript progress:** Step 1 (10-MC rules quiz) **PASSED**. Step 2 (transcribe `current-transcriber-test/22.mp3`, 77s bilingual skit) — ran end-to-end through the full pipeline; produces a complete, near-clean bilingual transcript (grade B; remaining: fillers, speaker-label split, one short mis-hear "Today English race"). The final submit/paste is the user's action.

**Open gaps (ranked):**
1. ~~Independent acoustic witness~~ **CLOSED** — 3-model consensus (Scribe+Deepgram+Whisper). Residual = brand-new proper nouns (sound-only) — but even "Sora" was consensus-confirmed by all 3.
2. **Stitch reliability** — Qwen reconciling the 2 language reads is unstable (swung between katakana-leak and dropped-JP); now bounded by `untranslated_english` + `completeness` but not bulletproof. Deterministic segment-replacement would be stronger.
3. **Paths don't compose** — `audit_transcript` (text) and `verify` (audio) still separate; `verify` ignores clean/full-verbatim mode.
4. **Silent no-op on missing data** — need a witness manifest (fail-loud).
5. **Wire kanji-readings + pitch-accent** (built but inert); weighted collocations; diverse (non-FLEURS) audio.

**Income context:** the real target is the **GoTranscript editor job** ($60–90/hr, edit AI transcripts, native English) and similar — the tool is a power-assist where the human (Alexander) reads/listens and verifies. Japanese is the hard proof-of-concept; English is where it pays. Do not re-pivot him off the build.

---

## 1. What this tool is

`~/Desktop/transcript-truth/` — a fork of **RoboTruth** ("no model in the verdict path" → deterministic transcription QA). It audits transcripts against style guidelines and surfaces likely errors. Originally aimed at unlocking paid Japanese transcription (GoTranscript $2.38/audio-min).

**Components built:**
| File | What it does | State |
|---|---|---|
| mechanical scanners | timestamps, speaker labels, inaudible/unintelligible, clean-verbatim fillers, spacing | 9 tests passing |
| `transcript_truth/semantic.py` | homophone (同音異義語) detector, SudachiPy-grounded, 197 trap-sets | coverage 6%→96% on test cases |
| `transcript_truth/disambiguate.py` | translate-and-check decision layer (LLM picks the coherent kanji) | 100% / 18 on minimal pairs |
| `transcript_truth/colloquial.py` | 11,154 JMdict slang/colloquial entries + contraction map | built |
| `transcript_truth/audio.py` | faster-whisper wrapper + cross-check | built |

**Knowledge bases (persisted in `data/`):**
- **Japanese:** `jp_confirmed.json` (340 homophone/rule entries), `jp_cases.json` (208 test cases), `jp_flagged.json` (9 rejected)
- **Spanish:** `es_confirmed.json` (267 entries), `es_cases.json` (220), `es_flagged.json` (3) — built this session

---

## 2. Background processes run this session

| Process | ID / file | Result |
|---|---|---|
| **Spanish KB build** (dynamic workflow: enumerate → adversarially verify → test → synth) | `wf_26c054a4-a6e` | ✅ 267 confirmed entries, 8 categories (homófonos, acentos, b/v, s/c/z, g/j/ll/y/h, falsos amigos, puntuación, ASR pairs), 220 test cases. Synth flagged it as a **candidate** KB (LLM-built + cross-checked, **not** authority-grounded — needs a RAE/wordfreq sweep). |
| **Real-audio loop** `bench/jp_audio_to_english.py` | FLEURS ja, 6 real clips | ✅ ran. Whisper `transcribe` (Japanese) + `translate` (English) on each clip. |
| **Real-audio CER benchmark** `bench/jp_realaudio.py` | — | ❌ failed (missing `torchcodec`); superseded by the loop above. |
| **Deterministic check** `bench/jp_deterministic_check.py` | OOV (SudachiPy) + frequency (wordfreq/MeCab) | ✅ ran on the 6 clips' actual Whisper output. |

Installed this session: `datasets`, `soundfile`, `librosa`, `wordfreq`, `mecab-python3`, `unidic-lite`, `ipadic`.

---

## 3. What was measured — the honest data

### Real Japanese audio (6 FLEURS clips, Whisper medium)
**2 of 6 fully correct, 4 of 6 had errors.** The errors, by type:

| Clip | Whisper heard | Truth | Error type |
|---|---|---|---|
| 3 | バルセ**アナ** / カタル**ネ**語 | バルセロナ / カタルーニャ語 | **garbled / non-word** |
| 4 | 数という葉 / 甲外 / 子立 / ねぎめちゃ | 鋭い歯 / 口蓋 / 歯列 / 逃げ道 | **garbled** |
| 5 | **時期判定** | **磁気反転** | **real word → real word** |
| 6 | **軍島** | **群島** | **real word → real word (homophone)** |

### How each verification layer did
- **English-translate cross-check:** caught clip 3 (English had "Barcelona/Catalan" while the Japanese was garbled → mismatch). **Missed clip 5** — Whisper mis-heard *and* mis-translated the same way (`時期判定` → "next judgment"), so the check agreed with the error. → **correlated blind spot.**
- **Deterministic OOV (does the word exist?):** caught `バルセアナ` (genuine — not a word). Missed `子立`/`ねぎめちゃ` (tokenized as known sub-words), `軍島` (in dictionary), `時期判定` (real word).
- **Deterministic OOV + frequency:** caught clip 3 (`バルセアナ` OOV + `カタルネ` rare). **False-alarmed** on `ファティマ` (Fatima — legitimate proper noun, just rare). Still missed `軍島` and `時期判定`. Lucky/wrong-reason flag on clip 5 (`ロスビー`, a correct-but-rare proper noun).

**Tally:** deterministic stack caught ~2/4 error clips, with false alarms on clean clips, and **missed every real-word-for-real-word swap.**

---

## 4. CORRECTION — the prior "Japanese can't work" conclusion was wrong, and now measurably so

_The earlier draft of this section declared Japanese verification impossible ("no deterministic rule can catch real-word swaps", "you cannot validate without reading Japanese"). That was defeatism dressed as rigor. It was refuted by **building the tool and running it.** 2026-06-19._

**The validation excuse was false.** You validate a tool you can't read the same way you validate code you can't read: **run it against a known-correct oracle.** FLEURS ships gold Japanese for every clip → catch-rate is objective string comparison against the label. No human Japanese literacy required, anywhere.

**What was actually built and run** (`transcript_truth/verdict.py` + `bench/run_two_layer.py`, real FLEURS audio, Whisper medium):

Two deterministic layers, **no model in the verdict path**:
1. **SOUND** — claim's reading (kana, via Sudachi) vs an independent ASR read of the audio. Mismatch = mishearing. → flagged **17 real mishearings** across 12 clips.
2. **HOMOPHONE** — identical reading, different kanji → JMdict decides: one a real word + the other not → flag the non-word; both real → AMBIGUOUS (surface both glosses, never fake a verdict).

**Results (objective, oracle = FLEURS gold):**
- Reading-divergence catch rate: **17/20 ≈ 85% on content words** (adversarial audit, 2026-06-19). _Correction: an earlier draft headlined "44/47 = 94% (punctuation stripped)" — that was wrong. The 44/47 counted Whisper's punctuation inserts/deletes (Sudachi reads them as 記号) on BOTH sides of the ratio; ~27 of the 44 were punctuation, and the producing script never stripped them. Content-words-only is 17/20 ≈ 85%._
- **This is RECALL only, not validation.** The benchmark uses the gold transcript on both sides (gold locates the error spans AND supplies the answer key), so it measures "of spans gold already flagged wrong, how many does reading-divergence catch" — it says **nothing about false-positive rate** in real gold-free use. A precision test (gold-free, correct transcripts) is still TODO.
- The exact error the prior draft called an *"uncatchable real-word-for-real-word swap"* — `時期判定`→`磁気反転` — **was caught** (テイ≠テン shows up in the kana).
- The "true homophone" `群島`/`軍島` (declared impossible) was **caught deterministically by the dictionary** — 軍島 is not a real word.
- **Clean clips stayed clean** (clips 1, 2, 11 → empty receipt) — not a flag-everything tool.
- Every flag is kana + English JMdict glosses → **readable with zero Japanese.**

**Honest residual:** homophones where *both* forms are real words in context (`貿易商`/`貿易省`) — the dictionary can't break the tie, and neither can a human from audio alone, because the information genuinely isn't in the sound. These are **surfaced as AMBIGUOUS**, not silently passed.

**Platform reality still applies** (unchanged, and separate from whether the tool works):
- TranscribeMe's exam forbids AI (permanent-ban). _(TranscribeMe specifically — not confirmed for GoTranscript.)_

**Verdict (post-audit): the decision logic contains no model, and on one FLEURS/Whisper-medium run it caught ~85% of content-word reading-divergences on spans already known (from gold) to be errors.** That's a real, honestly-bounded recall result — NOT a full "validated verifier" claim (precision/false-positives untested). The design is sound; the earlier "validated, no Japanese reading needed" framing was overstated and has been corrected. "Japanese can't work at all" is still wrong; "it's a finished, validated tool" was also wrong.

---

## 5. Where it DOES work — English / Legal (the viable lane)

- **TranscribeMe Legal track is OPEN** with "virtually unlimited work": Legal Prequalification Exam → Legal Entrance Exam → probation → full team. (The standard **English Entrance Exam is CLOSED** until further notice.)
- Downloaded prep: `~/Downloads/T105_Legal Prequalification Exam Instructions (5_14_25).pdf` + `T105_CV for Legal TranscribeMe Style Guide (LPE 6_9_25).pdf`.
- **Why this works:** English is the user's native language → he reads every word → **full verification.** Whisper's English error rate is far lower (~5%). The tool's scanners handle the legal formatting (clean verbatim, speaker turns, timestamps).
- **The rule:** the exam itself is **no-AI — taken solo.** The tool's legitimate role: help *study* the style guide (allowed: SG reference, research, spell-check are all permitted) and check the user's *own* work.

**Spanish KB also built (267 candidate entries)** — same architecture, easier than Japanese (high-resource, Latin script), still needs RAE/wordfreq grounding before trusting.

---

## 6. Income context (the real reason this mattered)

- User owes **$3,000** with rent pressure — the driver behind the whole push on Japanese.
- **No instant-$3k path exists** anywhere in scope (consistent with prior finding: nothing here clears cash in 24h).
- **Real money lanes (legitimate, keepable):**
  - **Mercor** — model-evaluation contract, active, real hourly pay, the user's actual verifiable skill. Fastest real dollars.
  - **English / Legal transcription** — legit, ramps (exam → probation → weekly pay).
  - **Outreach contracts**, **eToro bug bounty** (pay-on-validation), finished **hackathon builds**.

---

## 7. File map

```
~/Desktop/transcript-truth/
  transcript_truth/   semantic.py, disambiguate.py, colloquial.py, audio.py, engine.py, types.py
  data/               jp_confirmed.json (340), jp_cases.json (208), jp_flagged.json (9)
                      es_confirmed.json (267), es_cases.json (220), es_flagged.json (3)
                      jmdict-eng-*.json
  bench/              jp_audio_to_english.py   (the audio→JA+EN loop, real audio)
                      jp_deterministic_check.py (OOV + frequency, the RoboTruth test)
                      jp_realaudio.py          (CER bench; needs torchcodec)
                      jp_benchmark.py, jmdict_validate.py, build_colloquial.py
  tests/              test_transcript_truth.py (9 passing)
  STATUS.md           ← this file

~/Downloads/          T105_Legal Prequalification Exam Instructions (5_14_25).pdf
                      T105_CV for Legal TranscribeMe Style Guide (LPE 6_9_25).pdf
                      Transcription guidelines (Japanese)/  (GoTranscript guidelines + 5 gold samples)
```

---

## 8. Bottom line (updated 2026-06-19)

- **Built + RUN:** a real, two-layer RoboTruth-for-transcription engine — SOUND (reading-divergence) + HOMOPHONE (JMdict-decided), no model in the verdict path. `transcript_truth/verdict.py`, `bench/run_two_layer.py`, `bench/jp_phonetic_validate.py`, `bench/jp_readaloud_coherence.py`.
- **Measured against gold (recall only):** **~85% of content-word reading-divergences** caught on known-error spans (corrected down from an inflated "94%" that counted punctuation); the two "uncatchable" cases from the prior draft (`時期判定`/`磁気反転` reading-diff, `群島`/`軍島` non-word) caught by their respective layers; genuinely-ambiguous homophones surfaced as AMBIGUOUS not hidden. Precision (false-positive rate) untested — TODO.
- **Retired:** the "Japanese can't work / can't be validated" verdict — refuted by running the tool against the FLEURS oracle, exactly as you validate code you can't read.
- **Path A DONE (2026-06-19):** fixed the two confirmed-broken scanners (fillers were English-only → now catch えー/えーと/あのー/なんか; spacing keyed on ASCII → now handles full-width 、。？), added 3 missing deterministic scanners (no_exclamation, terminal_punctuation, paragraph_length ≤250), and wired the homophone + colloquial layers into the graded receipt (severity "review" = surfaced, weight 0, never tanks the grade). 9 tests pass; English transcripts still grade A clean. The tool is now an honest Japanese QA *aid for a human listener* — not an autopilot.
- **Gap workflow verdict (6 agents, grounded):** the GoTranscript quiz grades *produced text*, and the high-impact calls (excessive-vs-meaningful filler, 偏在/遍在, particle choice) need *hearing the audio* — not closeable by any data artifact. So: don't chase autonomous quiz-pass; aim the tool where the user is the audio-judge (English/Legal, or JP-with-user-listening).
- **Dictionary upgraded (2026-06-19):** word-existence layer now uses **full JMdict (217k words)** + **JMnedict proper nouns** (`data/jp_name_surfaces.json`, 954k name surfaces, compacted from the 167MB raw). Recognizes loanwords/place names (バルセロナ, 九龍, ファティマ) that the 22k "common" slice false-flagged. `verdict.py` `name_index()` treats known names as real words. All deterministic, no AI. 12 tests pass.
- **Next (optional):** rank 5 OOV/non-word gate over whole transcript (catches 軍島-type non-words in text alone); collocation/n-gram layer for context homophones (still no-AI); read-aloud `say` round-trip; precision test (gold-free, the real false-positive measurement — still the key honest gap).
- **Separate track:** platform/income (Mercor, English/Legal) unchanged — that's about *where to sell it*, not whether it works.
