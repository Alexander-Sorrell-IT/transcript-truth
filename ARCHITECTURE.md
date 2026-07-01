# transcript-truth — how the whole system works

**Core principle: _models propose, a deterministic pure function owns the verdict._**
Every model (ASR, diarizer, LLM) only ever *proposes* text or a flag. The grade is computed by a
pure function over deterministic scanner flags — **no model is in the verdict path.**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ AUDIO IN  (30–60 min gig audio: legal, medical, general)                       │
└───────────────────────────────────┬────────────────────────────────────────────┘
                                     ▼
╔═══════════════ TRANSCRIPTION CORE (consensus.py, chunking.py) ═══════════════════╗
║                                                                                  ║
║  1. LANGUAGE DETECT (Deepgram) ─────────────► route to that language's ROSTER    ║
║                                                                                  ║
║  2. CHUNKING (chunking.py) — VAD cut at SILENCE (never mid-word) + overlap        ║
║        • a chunk comes back EMPTY  ─► SLOW-DOWN-AND-LISTEN  (time_stretch 0.8x)   ║
║        • a seam won't stitch       ─► BRIDGE CHUNK (cut_window) spliced through   ║
║                                                                                  ║
║  3. MULTI-MODEL WITNESSES vote (per-language ROSTER):                             ║
║        Deepgram · Gemini · ElevenLabs Scribe · local Whisper · MMS ·             ║
║        PhoWhisper · Seamless      ──► _splice (overlap-dedup) ──► full transcript ║
║                                                                                  ║
║  4. DIARIZATION (whole-file): Deepgram · pyannote · Scribe                        ║
║        ──► cross-diarizer consensus ──► speaker timeline ──► REFERENCE-MAP        ║
║            (chunked text inherits speakers by timestamp — measured 95.8%)         ║
║                                                                                  ║
╚═══════════════════════════════════╤══════════════════════════════════════════════╝
                                     ▼   TEXT  (+ speaker labels)
╔═══════════════ QA ENGINE  (engine.audit_transcript) ════════════════════════════╗
║                                                                                  ║
║   compose(language, domain)   ◄────── THE 2-PLUGIN SYSTEM ──────────────────────  ║
║                                                                                  ║
║   ┌──────────────────────┐        ┌─────────────────────────────────────────┐   ║
║   │  LANGUAGE PLUGIN (14) │   ×    │  DOMAIN PLUGIN  (built ONCE)            │   ║
║   │  en fr de pt es tr vi │        │                                         │   ║
║   │  ja ko ru uk ar hi ur │        │  UNIVERSAL CORE  (every language)       │   ║
║   │                       │        │   medical: dosage hygiene + UMLS* term  │   ║
║   │  spelling · script ·  │        │   legal:   timestamp format             │   ║
║   │  punctuation · that   │        │                                         │   ║
║   │  language's rules     │        │  + PER-LANGUAGE LAYER  (built as needed) │   ║
║   │                       │        │   medical[en]: ISMP abbrevs, RxNorm     │   ║
║   │                       │        │   legal[en]:   full TranscribeMe CVL     │   ║
║   └───────────┬───────────┘        └──────────────────┬──────────────────────┘   ║
║               └────────► merged Profile (scanners deduped) ◄───┘                 ║
║                                     ▼                                            ║
║   run_scanners(transcript)  ──►  FLAGS   { rule, severity, line, evidence, fix } ║
║                                     ▼                                            ║
║   grade_and_verdict()   ◄── PURE FUNCTION — deterministic, no model             ║
║                                     ▼                                            ║
║                              RECEIPT  { grade, score, flags, math }              ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  *UMLS is language-aware: verifies a diagnosis-context term in the transcript's OWN
   language (per-language trigger phrases) against multilingual UMLS. Built once, all langs.

┌───────────── REFERENCE DATA / APIs ─────────┐   ┌────────── UPDATE SYSTEM ──────────┐
│ RxNorm drug names   cached, --refresh-data  │   │ config.py  cadence: off / hourly / │
│ UMLS terminology    LIVE API (multilingual) │   │            daily / weekly / monthly │
│ wordfreq            per-language frequency  │   │ manifest.py plugin versions        │
│ ISMP "do not use"   bundled (US list)       │   │ update.py  check ─► apply from the │
│ TranscribeMe CVL    24-pg guide → scanners  │   │            private GitHub repo      │
└─────────────────────────────────────────────┘   │  --update  --update-check          │
                                                   │  --refresh-data  --update-status   │
                                                   └────────────────────────────────────┘
```

## The two halves
- **Transcription core** — turns audio into accurate text. Models *propose*; chunking + bridge +
  slow-listen recover hard audio; witnesses vote; diarization assigns speakers. Language-agnostic
  mechanics (they operate on audio), so every language benefits.
- **QA engine** — grades text against the rules. `language × domain` compose into one scanner set;
  a pure function computes the verdict from the flags. This is the "no model in the verdict" half.

## The 2-plugin system (why it composes)
`compose(lang, domain)` = the language plugin's scanners **+** the domain's universal core **+** that
domain's per-language layer (if built). A domain is **built once**; it adapts to each language via
(a) the universal core, (b) language-aware scanners (UMLS in the transcript's language, `wordfreq`
per language), and (c) a small per-language layer only where rules are genuinely language-specific
(ISMP = US, CVL = English). Adding a language never means rebuilding a domain.
