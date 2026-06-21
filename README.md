# transcript-truth

> **Did the transcript follow the guidelines?**
> A deterministic transcription-QA auditor. Paste a transcript → get a receipt: every
> guideline violation, cited at its line, with the fix — and a grade from a pure
> function. **No model in the verdict path.**

Forked from [RoboTruth](https://github.com/Alexander-Sorrell-IT/robotruth)'s engine.
RoboTruth answers *"did the AI's PR do only what it claimed?"* with deterministic
scanners and zero LLM in the verdict. transcript-truth applies the same spine to
transcription: deterministic **guideline scanners** read the transcript, a
pure-function grader emits the verdict.

## Why "no model in the verdict path" matters here

We learned this the hard way: an LLM asked to judge transcription guidelines was
**confidently wrong** — unanimous, "high confidence," still incorrect, with no way
for a non-expert to catch it. So the LLM is nowhere near the verdict. Only
deterministic rule hits are. Every flag is reproducible and points at a line.

## What it checks (the mechanical half — fully deterministic)

| Scanner | Catches |
|---|---|
| `timestamps` | timestamps not in `[HH:MM:SS]` form (parens, missing zero-pad) |
| `speaker_labels` | uncertain-speaker `?` misplaced (`Speaker? 1:` instead of `?Speaker 1:`) |
| `inaudible` | malformed `[inaudible/unintelligible HH:MM:SS]` tags (misspelled, missing timestamp) |
| `fillers` | Clean-Verbatim fillers left in (um, uh, you know, I mean, kind of, sort of) |
| `spacing` | double spaces, space before punctuation |

## The honest line (where to point it)

The scanners above are the **mechanical** half of any style guide — fully deterministic,
fully citable, and most of what fails a QA pass. The **semantic** half (is this the
right word for the meaning? does it read naturally?) is deliberately *not* automated:
that needs a human who can read the language.

- **English transcription / your AI-eval work** → you verify the semantic half yourself,
  so this tool is pure upside: it enforces the mechanics with zero false confidence.
- **A language you can't read** → the mechanical half still works, but the semantic half
  is the wall. Don't let any tool pretend otherwise.

## Run (point it at a file)

```bash
# default profile (Japanese + GoTranscript English)
python3 -m transcript_truth.cli samples/sample_clean_verbatim.txt
python3 -m transcript_truth.cli path/to/file.txt --full                    # full-verbatim (keeps fillers)

# TranscribeMe Clean Verbatim for Legal (CVL)
python3 -m transcript_truth.cli samples/sample_legal_cvl.txt --legal       # or --profile=legal
python3 -m transcript_truth.cli --list-profiles                            # see all profiles

# Thoth — deterministic auto-fix (writes <file>.thoth.txt, no model)
python3 -m transcript_truth.cli samples/sample_legal_cvl.txt --legal --thoth

python3 tests/test_transcript_truth.py     # default engine tests
python3 tests/test_legal.py                # CVL legal tests
python3 tests/test_personal.py             # personal-profile tests
python3 tests/test_thoth.py                # auto-fix tests
```

```python
from transcript_truth import audit_transcript
receipt = audit_transcript(open("file.txt").read(), profile="legal")       # or "default"
print(receipt.grade, [(f.line, f.label) for f in receipt.flags])
```

## Profiles — one plug-in per language / style guide

Each guideline is a drop-in **profile** in `transcript_truth/profiles/`. A profile bundles
the deterministic scanners that apply to it and self-registers at import time. To add a new
language or style guide, drop one file in that folder — nothing else changes:

```python
# transcript_truth/profiles/my_guide.py
from ._base import Profile, register
from ..my_rules import MY_SCANNERS
register(Profile(name="myguide", description="...", scanners=(*MY_SCANNERS,)))
```

| Profile | Covers |
|---|---|
| `default` (`jp`, `gotranscript`) | Japanese + GoTranscript English — the original engine |
| `legal` (`cvl`) | TranscribeMe **Clean Verbatim for Legal** (English) |
| `me` (`alex`, `personal`) | the `legal` profile **plus** one transcriber's own recurring slips |

The legal profile is a **separate** profile, not extra default scanners, because CVL
*contradicts* the GoTranscript rules: CVL writes `okay` (lowercase), keeps `yeah` and the
crutch words `you know`/`I mean`, omits only `uh/ah/um/er`, and writes `[inaudible]` with no
timestamp. Every legal flag cites its style-guide page (e.g. `[p.9]`).

> **Legal-exam boundary:** the TranscribeMe Legal Prequalification Exam is **no-AI, taken solo** —
> using AI to produce or check exam answers is a permanent block. These profiles are a **study /
> self-check aid** for the guide and your *own* practice transcripts (the SG, research, and
> spell-checkers are the explicitly *permitted* tools), not an exam autopilot.

## Thoth — deterministic auto-fix

The scanners *report*; **Thoth** *applies* the fix. It's the same spine — **no model** —
just the **same compiled patterns the scanners detect with, applied via `re.sub`**, so
detection and correction can never drift. It is **profile-agnostic**: it applies whatever
fixer set the chosen profile carries (`default` = language-safe filler removal, `legal` =
the full CVL "Redline" set, `me` = that plus personal apostrophe fixes).

```bash
python3 -m transcript_truth.cli file.txt --legal --thoth     # writes file.thoth.txt
```
```python
from transcript_truth.thoth import thoth
fixed, changes = thoth(open("file.txt").read(), profile="legal")
```

Only **deterministic, ~always-correct** fixes are applied. The semantic judgment calls
(`review`-tier: which homophone a sentence *means*, `cant`/`wont`, つなぎ言葉 that might be
real words) are **never auto-applied** — they stay flags for the human, the same boundary the
whole engine keeps. On the legal sample, Thoth takes the receipt **D → A**.

## Layout

```
transcript_truth/
  types.py          Flag / Line / Transcript / Receipt
  scanners.py       deterministic guideline scanners  (the rules)
  legal_rules.py    CVL legal scanners + Redline fixers
  personal_rules.py one transcriber's recurring slips + fixers
  grade.py          pure-function grade (A–F)          (the verdict)
  engine.py         ingest → scan → grade
  thoth.py          deterministic auto-fix             (apply the fix)
  cli.py            paste-a-file CLI receipt
  profiles/         one plug-in per language / style guide
tests/              55 passing tests
samples/            transcripts with planted violations
```

## Next surfaces (free, like RoboTruth)

The engine is import-once; the same `audit_transcript` can back a web paste-box, an
MCP server (`audit_transcript` exposed to Claude/Cursor), and an API — exactly how
RoboTruth ships one engine to web + MCP + CLI.
