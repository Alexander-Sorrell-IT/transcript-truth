"""Quicktate house format — from the actual typist guidelines (quicktate.zendesk.com,
captured from his typist account 2026-07-07; saved at job-autopilot/quicktate_guidelines_full.txt).

Quicktate is short voicemail/memo work and CONTRADICTS the long-form vendors on purpose:
  - unknown words = '****' (exactly four stars), NOT [inaudible]/[indiscernible]/____
  - a caller-spelled word is typed AS THE WORD — 'b-o-b-j-o-n-e-s' is explicitly WRONG
    (Rev/Scribie/DT all REQUIRE the hyphenated form; this is why site is its own axis)
  - uncertain-but-heard words get '(phonetic)' after them
  - unknown speakers = 'Next Speaker'
  - lists: no numbering, no bullets, first word capitalized
"""
from __future__ import annotations
import re
from .types import Flag, Transcript


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# --- unknown-word convention: **** only; other vendors' tags are wrong here
# [inaudible] IS Quicktate-valid for a GROUP of words (iDictate rule); **** is for a single
# word. Only OTHER vendors' conventions are flat wrong here.
_WRONG_UNKNOWN = re.compile(r"\[(indiscernible|unintelligible|crosstalk)[^\]]*\]|____+", re.I)
_STARS_WRONG = re.compile(r"(?<!\*)(\*{1,3}|\*{5,})(?!\*)")


def qt_unknown_words(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _WRONG_UNKNOWN.finditer(ln.text):
            out.append(_flag("qt_unknown", f"Quicktate marks unknown words with '****', not '{m.group(0)}'",
                             ln.n, m.group(0), "Type **** (exactly four stars)."))
        for m in _STARS_WRONG.finditer(ln.text):
            out.append(_flag("qt_unknown", "Unknown-word marker is EXACTLY four stars",
                             ln.n, m.group(0), "Type **** (four stars).", "review"))
    return out


# --- caller-spelled words are typed as the word, never letter-by-letter
_SPELLED = re.compile(r"\b(?:[A-Za-z][- ]){2,}[A-Za-z]\b")


def qt_spelled_words(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _SPELLED.finditer(ln.text):
            joined = re.sub(r"[- ]", "", m.group(0))
            out.append(_flag("qt_spelled", "NEVER type a spelled-out word with hyphens/spaces",
                             ln.n, m.group(0), f"Type the word itself: '{joined.lower()}'."))
    return out


# --- unknown speakers = 'Next Speaker'
_WRONG_SPEAKER = re.compile(r"^(Speaker\s*\d+|MALE\s*\d*|FEMALE\s*\d*|Interviewer|Interviewee)\s*:", re.I)


def qt_speakers(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        m = _WRONG_SPEAKER.match(ln.text)
        if m:
            out.append(_flag("qt_speaker", f"Quicktate labels unknown speakers 'Next Speaker', not '{m.group(1)}'",
                             ln.n, m.group(0), "Use 'Next Speaker'.", "review"))
    return out


# --- lists: no numbering / bullets
_NUMBERED = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+\S")


def qt_lists(t: Transcript) -> list[Flag]:
    out = []
    hits = [ln for ln in t.lines if _NUMBERED.match(ln.text)]
    if len(hits) >= 2:                              # 2+ consecutive-ish = a formatted list
        for ln in hits:
            out.append(_flag("qt_list", "Lists get NO numbers or bullets",
                             ln.n, ln.text.strip()[:30],
                             "One item per line, first word capitalized, nothing in front.", "review"))
    return out


# --- run-on sentences (explicitly called out in the guidelines)
def qt_runons(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        body = ln.text.strip()
        if len(body.split()) > 60 and body.count(".") == 0:
            out.append(_flag("qt_runon", "Run-on: 60+ words without a period",
                             ln.n, body[:50] + "…", "Break into sentences — QT flags whole-voicemail run-ons.",
                             "review"))
    return out


QT_SCANNERS = [qt_unknown_words, qt_spelled_words, qt_speakers, qt_lists, qt_runons]

from .domains import register_site

register_site(
    "quicktate",
    scanners=(),
    per_language={"en": tuple(QT_SCANNERS), "es": (qt_unknown_words, qt_spelled_words, qt_lists)},
    description="Quicktate voicemail format (**** unknowns, joined spelled words, Next Speaker)",
)
