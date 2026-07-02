"""Personal profile — Alex's recurring mechanical slips.

Derived from his own writing corpus (~/Documents/Build From Scratch Ideas/
Speeches-Stories): improvised speeches and short fiction where the *ideas* are
finished but the raw draft consistently drops apostrophes in contractions. This
is the same deterministic spine as the rest of the engine — every flag is a
regex hit cited at its line. It rides ON TOP of the legal (CVL) profile.

SCOPE, honestly: this catches only the mechanical, high-frequency, regex-able
slips. The things that make the writing *his* — the anaphora, the hairpin tonal
turns, the rawness — are NOT errors and are never touched. And the genuinely
semantic slips (comma splices, run-ons) aren't caught by this mechanical profile;
homophone-meaning calls are handled by the engine's coherence layer as 'review'
flags a human CONFIRMS. Cites [personal].
"""
from __future__ import annotations
import re
from .types import Flag, Transcript


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# Missing-apostrophe contractions he drops in raw drafts. Curated to surface
# forms that are NOT also ordinary English words, so flagging is safe.
# would've/could've/should've are omitted on purpose — the legal profile already
# rewrites those to 'would have' etc., so we don't double-flag.
_APOS = {
    "dont": "don't", "doesnt": "doesn't", "didnt": "didn't", "isnt": "isn't",
    "arent": "aren't", "wasnt": "wasn't", "werent": "weren't", "havent": "haven't",
    "hasnt": "hasn't", "hadnt": "hadn't", "wouldnt": "wouldn't", "couldnt": "couldn't",
    "shouldnt": "shouldn't", "mustnt": "mustn't", "aint": "ain't",
    "youre": "you're", "theyre": "they're", "ive": "I've", "youve": "you've",
    "weve": "we've", "theyve": "they've", "thats": "that's", "whats": "what's",
    "wheres": "where's", "hows": "how's", "theres": "there's", "heres": "here's",
    "hes": "he's", "shes": "she's",
}
_APOS_RX = re.compile(r"\b(" + "|".join(_APOS) + r")\b", re.I)

# These collide with real words (cant = tilt/jargon, wont = accustomed), so they
# are 'review', not hard flags — the tool never silently overrules the rare case.
_APOS_AMBIG = {"cant": "can't", "wont": "won't"}
_APOS_AMBIG_RX = re.compile(r"\b(" + "|".join(_APOS_AMBIG) + r")\b", re.I)

_IM = re.compile(r"\b[Ii]m\b")   # im / Im -> I'm  (not 'IM', the abbreviation)


def personal_apostrophes(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        x = ln.text
        for m in _APOS_RX.finditer(x):
            std = _APOS[m.group(0).lower()]
            out.append(_flag("me_apostrophe",
                             f"'{m.group(0)}' is missing its apostrophe — '{std}'", ln.n,
                             m.group(0), f"Contraction needs an apostrophe: '{std}'. [personal]"))
        for m in _IM.finditer(x):
            out.append(_flag("me_apostrophe", f"'{m.group(0)}' should be \"I'm\"", ln.n,
                             m.group(0), "Contraction of 'I am' is \"I'm\". [personal]"))
        for m in _APOS_AMBIG_RX.finditer(x):
            std = _APOS_AMBIG[m.group(0).lower()]
            out.append(_flag("me_apostrophe",
                             f"'{m.group(0)}' — likely missing apostrophe '{std}' (or the rare real word)",
                             ln.n, m.group(0),
                             f"If you mean the contraction, write '{std}'. [personal]", "review"))
    return out


PERSONAL_SCANNERS = [personal_apostrophes]


# --- Thoth fixers: apply the apostrophe corrections (review-tier cant/wont excluded) ---
from .legal_rules import _cased   # shared case-carry helper

PERSONAL_FIXERS = [
    (_APOS_RX, lambda m: _cased(m.group(0), _APOS[m.group(0).lower()])),
    (_IM, lambda m: "I'm"),
]
