# Model strategy — what we have, what to get, what money changes

## What we have now (witnesses)
| Model | Role | Cost | Status |
|---|---|---|---|
| Deepgram nova-3 | ASR + diarization, many langs | paid/min | works, reliable |
| Gemini 2.5 | multimodal ASR + diarization | free tier (429-limited) | works; pro rate-limited |
| ElevenLabs Scribe | ASR + diarization | credits | works (new key) |
| HF Whisper-large-v3 | ASR, all langs | free tier | **depleted (402)** |
| NVIDIA (key unused) | Parakeet/Canary ASR, Sortformer diar | free credits | **not wired (gRPC)** |
| Kiwi | Korean morphology | free/local | wired |
| **local Whisper** (faster-whisper large-v3) | ASR, all langs | **free/local** | **INSTALLED + wired as `whisper` witness (replaces HF 402); ~11s/clip on M1, model cached** |
| Silero VAD | chunk-at-silence | free/local | INSTALLED (not yet wired into chunking) |
| zeyrek | Turkish morphology | free/local | INSTALLED (not yet wired into tr_rules) |
| Stanza | multilingual NLP | free/local | INSTALLED (downloads per-lang on demand) |

### Needs YOU before I can wire them
- **pyannote** (diarization/voice-fingerprint): accept the gated license on its HF page while logged in, then give me a HF **read token** (current HF key is the depleted inference one). Then I wire speaker embeddings.
- **NVIDIA Parakeet/Canary**: choose **local (NeMo, heavy/free)** or **API (may need you to enable ASR in your NVIDIA account)**.
- **On-demand, no auth (say the word):** Meta MMS, Meta Seamless (~9GB), PhoWhisper (vi), CAMeL Tools (ar) — I pull these when you want them.

## The big insight: the highest-value upgrades are FREE and LOCAL
Money buys *volume/reliability* on the paid APIs. But the biggest capability jumps cost **nothing** —
run models **locally on the M1**, unlimited, no credits, no rate limits:

1. **Local Whisper** (`faster-whisper` / `whisper.cpp`) — replaces the flaky/depleted HF Whisper with a
   free, always-on witness in *every* language. **Do this first, regardless of money.** Kills the 402 wall.
2. **Speaker embeddings** (`pyannote` / `resemblyzer` / SpeechBrain) — local, free. Unlocks the
   huge-file diarization backstop (Phase 0) and strengthens cross-diarizer consensus. The "voice
   fingerprint" we said we'd need.
3. **Per-language local analyzers** (like Kiwi): CAMeL Tools (Arabic morphology), indic-nlp/stanza
   (Hindi/Urdu). Free; sharpen the deterministic rules.

## Per-language specialized ASR (open, run locally — directly answers Phase 5)
The general roster is weakest on the hard languages. Open, free, language-specialized Whisper variants:
- **Vietnamese:** PhoWhisper (VinAI)
- **Hindi/Urdu/Indic:** AI4Bharat IndicWhisper / IndicConformer
- **Arabic:** Arabic-finetuned Whisper (e.g. tarteel)
- **Korean:** Korean-finetuned Whisper (Kiwi already handles the morphology/verdict side)
These plug in as just another roster witness per language.

## Paid / API models worth adding (chosen by MEASUREMENT, not bought blindly)
We already have 4 witnesses + 2-3 diarizers — *text* consensus is well-covered, so more general ASR
APIs hit diminishing returns. Where paid APIs still add REAL value:
- **A 3rd independent diarizer — AssemblyAI or Speechmatics** — the highest-value add: diarization
  (not text) is the weak spot (Deepgram+Scribe agreed only 63% on hard crosstalk; a 3rd breaks ties).
- **NVIDIA Parakeet/Canary** — key already in hand; wire the endpoint (near-free).
- **DeepL API** (translation) — best-in-class for the EN→X track (Phase 8); has a free tier.
- **Per-language API** (Speechmatics on accents, Google STT on some langs) — ONLY where the battery
  shows a gap. Targeted, not blanket.
- **OpenAI gpt-4o-transcribe** — another strong general witness (only if the battery says it helps).

**Rule:** before paying for any model, run it on the Phase-1 battery and keep it only if it moves
WER/diarization for that language. A measured system, not an expensive one.

## How money actually changes things (honest, per provider)
- **ElevenLabs:** $ = more Scribe credits (linear per audio-minute). Removes the credit wall.
- **Gemini:** paid tier removes the **429 rate limits** → gemini-2.5-**pro** becomes reliable (better diarization).
- **Deepgram:** pay-per-minute already; $ = more volume, no throttling.
- **HF:** $ = inference credits — **but skip it**, run Whisper locally for free instead.
- **Net:** money mainly removes *credit/rate walls* on the paid APIs. It does **not** unlock new
  capability that local free models can't. So: **build the free local stack first; spend money on
  volume once it's in.**

## Fuller catalog of FREE / open models (run local on the M1)

### General ASR (multi-language, free)
- **Whisper large-v3 / large-v3-turbo** (faster-whisper, whisper.cpp) — the workhorse, all langs.
- **Meta MMS** — ASR for **1000+ languages**; the answer for rare/hard langs the roster is thin on.
- **Meta SeamlessM4T / Seamless** — multilingual ASR **+ speech translation** (directly serves EN→X, Phase 8).
- **NVIDIA Parakeet** (tdt-1.1b) — very fast, top English; **Canary-1b** — multilingual ASR+translation (NeMo, open; we also hold an NVIDIA key).
- **wav2vec2 / XLS-R** (Meta) — multilingual, fine-tunable. **Distil-Whisper / Moonshine** — fast/edge English.

### Diarization & speaker embeddings (free)
- **pyannote.audio** — segmentation + speaker embeddings (HF-gated, free). The standard.
- **NVIDIA Sortformer / NeMo diarization**; **SpeechBrain ECAPA-TDNN**; **WeSpeaker**; **resemblyzer** — all open speaker-embedding options for the voice-fingerprint backstop + better consensus.

### Preprocessing (free, cheap, high-leverage)
- **Silero VAD** — voice-activity detection → **chunk at silence, not mid-word** (fixes seam loss at the source).
- noise suppression (RNNoise/Demucs) → helps the low-SNR battery case.

### Language ID (free)
- Whisper built-in; **Meta MMS-LID** (4000+ langs); SpeechBrain lang-id → a 2nd detector to vote with Deepgram.

### Per-language specialized ASR (open)
- **Vietnamese:** PhoWhisper (VinAI) · **Hindi/Urdu/Indic:** AI4Bharat IndicWhisper / IndicConformer (22 langs)
- **Arabic:** ArTST, tarteel whisper-ar · **Korean:** Whisper-ko (+ Kiwi for morphology, have it)
- **Japanese:** ReazonSpeech (+ MeCab/fugashi) · **Russian:** GigaAM (Sber, open) · **Turkish/Spanish/French/German/Portuguese:** Whisper + wav2vec2 fine-tunes (strong already)

### Per-language NLP analyzers (free, local — like Kiwi/pymorphy)
- **Arabic:** CAMeL Tools, Farasa · **Hindi/Indic:** indic-nlp-library, Stanza, iNLTK
- **Turkish:** Zemberek / zeyrek · **Korean:** Kiwi (have), KoNLPy · **Japanese:** MeCab/fugashi (have), SudachiPy
- **Russian/Ukrainian:** pymorphy3 (have) · **General:** Stanza (60+ langs), spaCy · Hunspell dicts (many langs)

**Top free picks by leverage:** local Whisper → Silero VAD (better seams) → pyannote embeddings →
MMS/Seamless for hard langs + translation → per-language analyzers (CAMeL/Stanza/Zemberek) to sharpen rules.

## Priority order
1. Local Whisper (free, unblocks HF wall, all langs) →
2. Speaker embeddings (free, huge-file diarization + better consensus) →
3. Per-language local Whisper variants for ar/hi/ur/vi (free, the real Phase-5 quality fix) →
4. Wire NVIDIA (near-free, key in hand) →
5. Then paid: AssemblyAI / OpenAI / more ElevenLabs+Gemini-pro credits for volume.
