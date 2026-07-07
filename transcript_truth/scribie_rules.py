"""Scribie.com house format — from Scribie's PUBLIC transcriber guide (+ delivered-format
blog), fetched & verified 2026-07-07. Scribie's DELIVERED format: Speaker N labels,
paragraph timestamps, [laughter]/[chuckle] only, blanks as ____, contractions NOT expanded
(the exact opposite of Rev), 'etcetera' spelled out, no periods in acronyms."""
from __future__ import annotations
import re
from .types import Flag, Transcript


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# --- tag vocabulary: ONLY [laughter]/[chuckle]; everything else is a blank ____ (SCR-TAG-01..03)
_TAG = re.compile(r"\[([a-z][a-z :\d-]{1,30})\]", re.I)
_ALLOWED = {"laughter", "chuckle"}


def scribie_tags(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _TAG.finditer(ln.text):
            tag = m.group(1).strip().lower()
            if tag in _ALLOWED:
                continue
            if tag.startswith(("inaudible", "indiscernible", "crosstalk", "phonetic", "unintelligible")):
                out.append(_flag("scribie_tag", f"Scribie marks inaudible speech with a blank '____', not '[{tag}]'",
                                 ln.n, m.group(0), "Replace the tag with ____ (underscores)."))
            else:
                out.append(_flag("scribie_tag", f"'[{tag}]' is not a Scribie tag",
                                 ln.n, m.group(0), "Scribie allows only [laughter] and [chuckle].", "review"))
    return out


# --- expanded informal contractions (SCR-ACC-02: wanna/gonna/kinda/gotta must NOT be expanded).
# Expansion is undetectable from text alone, so this scanner protects the other direction:
# nothing to flag — but 'etc.' and dotted acronyms ARE checkable style rules (SCR-STY-01, SCR-PUNC-03).
_ETC = re.compile(r"\betc\.?(?=[\s,.]|$)", re.I)
_DOTTED_ACRONYM = re.compile(r"\b(?:[A-Za-z]\.){2,}(?![A-Za-z])")
_DOTTED_OK = {"i.e.", "e.g.", "a.m.", "p.m.", "u.s.", "a.d.", "b.c."}


def scribie_style(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _ETC.finditer(ln.text):
            out.append(_flag("scribie_style", "'etc.' must be written 'etcetera'",
                             ln.n, m.group(0), "Scribie style: etcetera."))
        for m in _DOTTED_ACRONYM.finditer(ln.text):
            if m.group(0).lower() in _DOTTED_OK:
                continue
            out.append(_flag("scribie_style", f"No periods in acronyms ('{m.group(0)}')",
                             ln.n, m.group(0), f"Write '{m.group(0).replace('.', '')}'.", "review"))
    return out


# --- speaker labels: delivered format is 'Speaker N:' (SCR-SPK-02)
_BAD_SPEAKER = re.compile(r"^(interviewer|interviewee|respondent|person \d+|male|female)\s*:", re.I)


def scribie_speakers(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        m = _BAD_SPEAKER.match(ln.text)
        if m:
            out.append(_flag("scribie_speaker", f"Scribie labels unnamed speakers 'Speaker 1/2/…', not '{m.group(1)}'",
                             ln.n, m.group(0), "Use Speaker N in order of first appearance.", "review"))
    return out


# --- spelled-out names all caps hyphen-separated (SCR-CAP-02) — same shape as Rev's rule
_SPELLED_LOWER = re.compile(r"\b([a-z]-(?:[a-z]-){1,}[a-z])\b")


def scribie_spelled_names(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _SPELLED_LOWER.finditer(ln.text):
            out.append(_flag("scribie_spelled", "Spelled-out names are all caps (A-D-A-M)",
                             ln.n, m.group(1), f"Write '{m.group(1).upper()}'."))
    return out


SCRIBIE_SCANNERS = [scribie_tags, scribie_style, scribie_speakers, scribie_spelled_names]

from .domains import register_site

register_site(
    "scribie",
    scanners=(),
    per_language={"en": tuple(SCRIBIE_SCANNERS)},
    description="Scribie.com delivered format (Speaker N, ____ blanks, [laughter]/[chuckle] only)",
)
