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

## Run

```bash
python3 -m transcript_truth.cli samples/sample_clean_verbatim.txt          # clean-verbatim audit
python3 -m transcript_truth.cli path/to/file.txt --full                    # full-verbatim (keeps fillers)
python3 tests/test_transcript_truth.py                                     # 9 tests
```

```python
from transcript_truth import audit_transcript
receipt = audit_transcript(open("file.txt").read(), mode="clean_verbatim")
print(receipt.grade, [(f.line, f.label) for f in receipt.flags])
```

## Layout

```
transcript_truth/
  types.py        Flag / Line / Transcript / Receipt
  scanners.py     deterministic guideline scanners  (the rules)
  grade.py        pure-function grade (A–F)          (the verdict)
  engine.py       ingest → scan → grade
  cli.py          paste-a-file CLI receipt
tests/            9 passing tests
samples/          a transcript with planted violations
```

## Next surfaces (free, like RoboTruth)

The engine is import-once; the same `audit_transcript` can back a web paste-box, an
MCP server (`audit_transcript` exposed to Claude/Cursor), and an API — exactly how
RoboTruth ships one engine to web + MCP + CLI.
