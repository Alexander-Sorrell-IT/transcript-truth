"""Allegis Transcription house format — from their PUBLIC Legal Transcription Guide
(16-page PDF) + assessment style guide, both fetched and read in full 2026-07-07.

Insurance/legal EUO-deposition style. Key conventions (and conflicts with other vendors):
  - Q / A speaker labels with NO COLON in legal work (assessment uses Q:/A:)
  - colloquy = MR./MS. LASTNAME: + two spaces; unknowns = UNIDENTIFIED SPEAKER_#
  - allowed tags: [inaudible], [ph], [sic], [No audible response.]
  - BANNED in legal: [sounds like], [crosstalk], [RD], [laughs]
  - informal contractions expanded (gonna->going to) BUT 'cause is CORRECT (never 'cuz)
  - '--' interruptions (like DT/TranscribeMe; opposite of Rev)
  - NO inline timestamps (times live on the worksheet — opposite of Rev/DT)
  - pauses are never indicated
"""
from __future__ import annotations
import re
from .types import Flag, Transcript


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# --- tag vocabulary
_TAG = re.compile(r"\[([a-z][a-z .]{1,28})\]", re.I)
_ALLOWED = {"inaudible", "ph", "sic", "no audible response."}
_BANNED = {"sounds like": "not used in legal transcripts", "crosstalk": "not used — transcribe what is discernible",
           "rd": "not used", "laughs": "not used", "laughing": "not used", "laughter": "not used",
           "indiscernible": "Allegis uses [inaudible]", "unintelligible": "Allegis uses [inaudible]",
           "phonetic": "Allegis uses [ph] after the word"}


def al_tags(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _TAG.finditer(ln.text):
            tag = m.group(1).strip().lower()
            if tag in _ALLOWED:
                continue
            if tag in _BANNED:
                out.append(_flag("al_tag", f"'[{tag}]' — {_BANNED[tag]}",
                                 ln.n, m.group(0), "Allegis legal tags: [inaudible], [ph], [sic], [No audible response.]"))
            else:
                out.append(_flag("al_tag", f"'[{tag}]' is not an Allegis tag",
                                 ln.n, m.group(0), "Allowed: [inaudible], [ph], [sic], [No audible response.]", "review"))
    return out


# --- Q/A labels: NO colon in legal format
_QA_COLON = re.compile(r"^\s*(Q|A):\s")


def al_qa_labels(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        m = _QA_COLON.match(ln.text)
        if m:
            out.append(_flag("al_qa", f"Legal format: '{m.group(1)}' takes NO colon",
                             ln.n, m.group(0).strip(),
                             f"Write '{m.group(1)}  ' (label, two spaces, no colon).", "review"))
    return out


# --- informal contractions expanded; okay/all right forms; 'cause is correct, 'cuz is not
_INFORMAL = re.compile(r"\b(gonna|wanna|gotta|ain't|would've|could've|should've|'?cuz)\b", re.I)
_FIX = {"gonna": "going to", "wanna": "want to", "gotta": "got to", "ain't": "am not",
        "would've": "would have", "could've": "could have", "should've": "should have",
        "cuz": "'cause", "'cuz": "'cause"}
_OK_WRONG = re.compile(r"\bO[Kk]\b|\bm'?kay\b|\balright\b")


def al_contractions(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _INFORMAL.finditer(ln.text):
            w = m.group(1).lower()
            out.append(_flag("al_contraction", f"Expand '{m.group(1)}'",
                             ln.n, m.group(1), f"Write '{_FIX.get(w, w)}'."))
        for m in _OK_WRONG.finditer(ln.text):
            good = "okay" if m.group(0).lower() in ("ok", "m'kay", "mkay") else "all right"
            out.append(_flag("al_spelling", f"'{m.group(0)}' — Allegis writes '{good}'",
                             ln.n, m.group(0), f"Write '{good}'."))
    return out


# --- numbers: leading zero below 1; no sentence-initial numerals
_NAKED_POINT = re.compile(r"(?<![\d.])\.(\d+)\b")
_SENTENCE_NUMERAL = re.compile(r"(?:^|[.!?]\s+)(\d+)\b")


def al_numbers(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        body = ln.text
        for m in _NAKED_POINT.finditer(body):
            out.append(_flag("al_number", f"Leading zero required: '0.{m.group(1)}'",
                             ln.n, m.group(0), "'Point five' -> 0.5."))
        for m in _SENTENCE_NUMERAL.finditer(body):
            out.append(_flag("al_number", "Never start a sentence with a numeral",
                             ln.n, m.group(0).strip(), "Spell the number out at sentence start.", "review"))
    return out


# --- interruptions '--'; em-dash banned (Word autocorrect artifact); no inline timestamps
_EMDASH = re.compile(r"[—–]")
_INLINE_TS = re.compile(r"\[?\b\d{2}:\d{2}:\d{2}\b\]?")


def al_format(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        if _EMDASH.search(ln.text):
            out.append(_flag("al_dash", "Em/en dash — Allegis uses two hyphens '--' (disable Word autocorrect)",
                             ln.n, _EMDASH.search(ln.text).group(0), "Write '--'."))
        for m in _INLINE_TS.finditer(ln.text):
            out.append(_flag("al_timestamp", "No inline timestamps — times go on the Transcriber Worksheet",
                             ln.n, m.group(0), "Remove; log inaudibles/[sic] times on the worksheet.", "review"))
    return out


AL_SCANNERS = [al_tags, al_qa_labels, al_contractions, al_numbers, al_format]

from .domains import register_site

register_site(
    "allegis",
    scanners=(),
    per_language={"en": tuple(AL_SCANNERS)},
    description="Allegis Transcription legal format (Q/A no-colon, [inaudible]/[ph]/[sic], no inline timestamps)",
)
