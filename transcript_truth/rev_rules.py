"""Rev.com house format — from Rev's PUBLIC Transcription Style Guide (v5 + v4.0.2 PDFs,
fetched & verified 2026-07-07). Scanners cover the mechanically checkable rules; a rule
supported in v4 but dropped in v5 accepts the union (guide note: [crosstalk]/[phonetic]).

Where Rev CONFLICTS with other vendors (this is why 'site' is its own axis):
  - interruption = single hyphen at cutoff (DT/TranscribeMe use '--')
  - informal contractions ARE formalized in non-verbatim (Scribie forbids expanding them)
  - tags are [inaudible hh:mm:ss] WITH timestamp (DT uses bare [indiscernible])
"""
from __future__ import annotations
import re
from .types import Flag, Transcript


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# --- tag vocabulary: bracketed tags need an hh:mm:ss timestamp (REV-TAG-01..05)
_BR_TAG = re.compile(r"\[([a-z][a-z ]{1,25}?)(?:\s+(\d{2}:\d{2}:\d{2}))?\]", re.I)
_BR_ALLOWED = {"inaudible", "crosstalk", "foreign language", "phonetic"}
_PAREN_TAG = re.compile(r"\(([a-z]{2,15})\)", re.I)
_PAREN_ALLOWED = {"laughs", "laughing", "beep", "censored", "singing", "silence",
                  "affirmative", "negative"}


def rev_tags(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _BR_TAG.finditer(ln.text):
            tag, ts = m.group(1).strip().lower(), m.group(2)
            known = tag in _BR_ALLOWED or tag.istitle() or tag in ("spanish", "french", "german")
            if tag in _BR_ALLOWED and not ts:
                out.append(_flag("rev_tag", f"'[{tag}]' needs an hh:mm:ss timestamp",
                                 ln.n, m.group(0), f"Rev format: [{tag} 00:10:05]."))
            elif tag not in _BR_ALLOWED:
                out.append(_flag("rev_tag", f"'[{tag}]' is not a Rev tag",
                                 ln.n, m.group(0),
                                 "Rev bracketed tags: [inaudible hh:mm:ss], [crosstalk hh:mm:ss], "
                                 "[foreign language hh:mm:ss], [phonetic hh:mm:ss].", "review"))
        for m in _PAREN_TAG.finditer(ln.text):
            tag = m.group(1).lower()
            if tag in ("laughter", "chuckle", "coughs", "coughing", "applause", "clapping"):
                out.append(_flag("rev_tag", f"'({tag})' is not a Rev parenthetical",
                                 ln.n, m.group(0),
                                 "Rev allows (laughs)/(laughing)/(beep)/(censored)/(singing); other "
                                 "non-speech sounds are not transcribed.", "review"))
    return out


# --- affirmative/negative utterances need their qualifier (REV-TAG-09)
_MMHMM = re.compile(r"\b(Mm-hmm|Mm-mm|Uh-huh|Uh-uh)\b(?!\s*\((affirmative|negative)\))", re.I)


def rev_affirmative(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _MMHMM.finditer(ln.text):
            w = m.group(1)
            q = "affirmative" if w.lower() in ("mm-hmm", "uh-huh") else "negative"
            out.append(_flag("rev_affirmative", f"'{w}' needs its qualifier",
                             ln.n, w, f"Rev format: {w} ({q}).", "review"))
    return out


# --- ellipsis / interruption punctuation (REV-PUNC-01..03)
_ELLIPSIS_NOSPACE = re.compile(r"(\.\.\.|…)(?=[^\s.\"'])")
_DOUBLE_DASH = re.compile(r"\w--(?:\s|$)")


def rev_punctuation(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _ELLIPSIS_NOSPACE.finditer(ln.text):
            out.append(_flag("rev_punct", "Ellipsis must be followed by a space",
                             ln.n, ln.text[max(0, m.start()-8):m.end()+6],
                             "Rev: 'this is… no' (space after the ellipsis).", "review"))
        if _DOUBLE_DASH.search(ln.text):
            out.append(_flag("rev_punct", "Rev marks interruptions with a single hyphen, not '--'",
                             ln.n, _DOUBLE_DASH.search(ln.text).group(0).strip(),
                             "Rev: 'I couldn't wait-' (single hyphen at the cutoff)."))
    return out


# --- spelled-out words are UPPERCASE letter-hyphen-letter (REV-PUNC-06)
_SPELLED_LOWER = re.compile(r"\b([a-z]-(?:[a-z]-){1,}[a-z])\b")


def rev_spelled_words(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _SPELLED_LOWER.finditer(ln.text):
            out.append(_flag("rev_spelled", "Spelled-out words are uppercase (W-O-R-D)",
                             ln.n, m.group(1), f"Write '{m.group(1).upper()}'."))
    return out


# --- informal contractions are formalized in non-verbatim (REV-ACC-03); mode-gated
_INFORMAL = re.compile(r"\b(gonna|wanna|gotta|kinda|sorta|'cause|cuz|doin'|goin'|'em)\b", re.I)


def rev_informal_contractions(t: Transcript) -> list[Flag]:
    if getattr(t, "mode", "clean_verbatim") == "verbatim":
        return []                                   # verbatim keeps them exactly as spoken
    fix = {"gonna": "going to", "wanna": "want to", "gotta": "got to", "kinda": "kind of",
           "sorta": "sort of", "'cause": "because", "cuz": "because", "doin'": "doing",
           "goin'": "going", "'em": "them"}
    out = []
    for ln in t.lines:
        for m in _INFORMAL.finditer(ln.text):
            w = m.group(1).lower()
            out.append(_flag("rev_contraction", f"Non-verbatim formalizes '{m.group(1)}'",
                             ln.n, m.group(1), f"Write '{fix.get(w, w)}'."))
    return out


REV_SCANNERS = [rev_tags, rev_affirmative, rev_punctuation, rev_spelled_words,
                rev_informal_contractions]

from .domains import register_site

register_site(
    "rev",
    scanners=(),
    per_language={"en": tuple(REV_SCANNERS)},       # Rev is an English-work platform
    description="Rev.com format (timestamped tags, single-hyphen interruptions, qualifier utterances)",
)
