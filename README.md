# transcript-truth

> **Multi-model transcription + deterministic QA.**
> Audio in → an accurate transcript (many models vote, hard audio recovered) → a receipt:
> every guideline violation cited at its line, with the fix, and a grade from a pure function.
> **Models propose; a deterministic pure function owns the verdict.**

Full system map + model list: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## Install on a new machine

```bash
git clone https://github.com/Alexander-Sorrell-IT/transcript-truth.git
cd transcript-truth
bash setup.sh --models     # deps + bundled data + free local models + full self-test
# then paste your API keys into .env (cloud witnesses; optional — local models need none)
```

Works CPU-only (no GPU required): local Whisper auto-selects **faster-whisper int8** on plain
CPUs (16GB+ RAM fine) and **mlx-whisper** (Metal) on Apple Silicon. Windows: use WSL.
Japanese data (JMdict-common + JMnedict names + collocations + pitch accent, © EDRDG CC BY-SA)
ships in the repo; `setup.sh` fetches the optional full JMdict for max coverage.

## The two halves

**1. Transcription core** — audio → accurate text.
Multi-model ASR consensus (Deepgram · Gemini · ElevenLabs Scribe · Whisper · Meta MMS · PhoWhisper · Seamless) vote per-language; VAD chunking with **bridge chunks** + **slow-down-and-listen** recover hard audio; whole-file **diarization** (Deepgram · pyannote · Scribe) assigns speakers via a reference map. Models *propose* the text.

**2. QA engine** — text → grade.
The **2-tier plugin system** (`language × domain`) scans the transcript; a pure function grades the flags.

## Models propose, the verdict is deterministic

Models are **integral to detection** — they transcribe, and they propose flags (e.g. the homophone witness). But the **grade** is a pure function over the flags. Model-proposed flags are **`review` tier** (advisory: they surface for a human and cap the grade at B, but never enter the hard error score). So: *models everywhere in detection, no model in the verdict math.*

---

## USE IT CORRECTLY — the 2-tier stack, models on

```python
from transcript_truth import audit_transcript

# FULL STACK: language tier × domain tier, with the model checks ON
receipt = audit_transcript(text, profile="en", domain="legal", coherence=True)
print(receipt.grade, [(f.line, f.rule, f.label) for f in receipt.flags])
```

- **`profile`** = the **LANGUAGE tier** — one of 14 (`en`, `fr`, `de`, `pt`, `es`, `tr`, `vi`, `ja`, `ko`, `ru`, `uk`, `ar`, `hi`, `ur`). Handles *that language's* grammar / spelling / script / homophones.
- **`domain`** = the **DOMAIN tier** — `legal` (TranscribeMe CVL) or `medical` (RxNorm + ISMP + UMLS). Sits **on top** of any language.
- **`coherence=True`** = turn the **model checks ON** (homophone witness, etc.). This is what catches its/it's, affect/effect, their/there.

> ⚠️ **Common mistake (don't do this):** `audit_transcript(text, profile="legal")` runs the CVL *formatting* scanners **only** — no language grammar, no models. It will miss homophones and general grammar. Always compose the **language tier** and pass **`coherence=True`** unless you specifically want formatting-only.

**Rule of thumb:** to check anything for real, use the full stack — `profile=<language>, domain=<domain>, coherence=True`. That's what the engine is.

---

## The 2-tier plugin system

`compose(language, domain)` merges: the **language tier's** scanners **+** the **domain's universal core** (all languages) **+** the domain's **per-language layer** (built where rules are language-specific), deduped into one Profile.

- **A domain is built ONCE** and composes with every language. It adapts via (a) the universal core, (b) language-aware scanners (UMLS verifies in the transcript's own language; `wordfreq` scores frequency per-language), and (c) a small per-language layer only where rules are genuinely language-specific (ISMP = US, CVL = English).
- Adding a language never rebuilds a domain; adding a domain never touches the languages.

| Domain | Universal core (all languages) | Per-language layer |
|---|---|---|
| **legal** | timestamp format | **en:** full TranscribeMe CVL (caps, spelling, titles, tags, numbers, dashes, Latin terms) |
| **medical** | dosage-number hygiene (locale-safe) + **multilingual UMLS** terminology | **en:** ISMP dangerous abbreviations + RxNorm drug names |

## CLI

```bash
python3 -m transcript_truth.cli file.txt --profile=en --domain=legal   # full stack
python3 -m transcript_truth.cli file.txt --legal --thoth               # + deterministic auto-fix
python3 -m transcript_truth.cli --list-profiles
python3 -m transcript_truth.cli --update-check                         # plugin updates (see below)
```

## Reference data / APIs (data, not models)

RxNorm drug names (cached, `--refresh-data`) · **UMLS** medical terminology (live licensed API, multilingual) · `wordfreq` (per-language frequency) · ISMP "Do Not Use" list · the 24-page TranscribeMe CVL guide → scanners.

## Update system (plugin cadence)

`config.py` sets a cadence (**off / hourly / daily / weekly / monthly**); `manifest.py` tracks plugin versions; `update.py` pulls newer/new plugins from the source repo (authenticated GitHub API). New languages and new domain coverage ship as plugin updates — `--update`, `--update-check`, `--refresh-data`, `--set-update-frequency`.

## Thoth — deterministic auto-fix

The scanners *report*; **Thoth** *applies* the fix — the **same compiled patterns**, applied via `re.sub`, so detection and correction can't drift. Profile-agnostic (applies the chosen profile's fixer set). Only deterministic, ~always-correct fixes are applied; semantic/`review`-tier judgment calls stay flags for the human.

```python
from transcript_truth.thoth import thoth
fixed, changes = thoth(open("file.txt").read(), profile="legal")
```

## Layout

```
transcript_truth/
  consensus.py      multi-model ASR consensus + chunking/bridge/relisten + diarization
  chunking.py       VAD chunking, time-stretch (slow-listen), bridge windows
  witness.py        the ASR/diarizer model adapters
  language.py       language auto-detect + routing
  engine.py         audit_transcript: ingest → compose(language×domain) → scan → grade
  domains.py        the DOMAIN tier (legal, medical) — universal core + per-language layers
  profiles/         the LANGUAGE tier — one plug-in per language (14)
  legal_rules.py / tm_legal.py   CVL legal scanners + fixers
  medical_rules.py / umls.py     medical scanners + UMLS verification
  grade.py          pure-function grade (A–F)  (the verdict)
  thoth.py          deterministic auto-fix
  config.py / manifest.py / update.py   plugin update system
tests/              128 passing tests
```

> **Legal-exam note:** the TranscribeMe Legal Prequalification Exam is **no-AI, taken solo** — the
> style guide, research, and spell-checkers are the *permitted* tools. The engine is a **study /
> self-check aid** for the guide and your **own practice transcripts**. Know your own risk on the live exam.
