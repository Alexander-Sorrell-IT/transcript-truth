"""Cyrillic script-integrity checks — deterministic, no model, no wordlist.

The single most common machine-transcription error in Cyrillic text is the
Latin/Cyrillic HOMOGLYPH: a Latin letter that is a visual twin of a Cyrillic one
slips into a word (Latin a A e E o O c C p P x X y -> Cyrillic а е о с р х у …).
A single word containing BOTH scripts is almost always such an error.

Unlike the homophone surfacers (es_rules / semantic), this needs no authority
KB — mixed script inside one token is unambiguously wrong — so it is a HARD
`moderate` error, not `review`. Works for any Cyrillic language (ru, uk, be, …).
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

_CYR = re.compile(r"[Ѐ-ӿ]")          # Cyrillic block
_LAT = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)    # a run of letters (any script)


def mixed_script(t: Transcript) -> list[Flag]:
    """Flag any single token that mixes Latin and Cyrillic letters — a homoglyph error."""
    out = []
    for ln in t.lines:
        for m in _WORD.finditer(ln.text):
            w = m.group(0)
            if _CYR.search(w) and _LAT.search(w):
                lat = "".join(ch for ch in w if _LAT.match(ch))
                out.append(Flag(
                    rule="cyrillic_mixed_script", severity="moderate", line=ln.n, evidence=w,
                    label=f"mixed Latin/Cyrillic in one word: '{w}' (Latin chars: {lat}) — homoglyph error",
                    fix="Replace the Latin look-alike letters with their Cyrillic equivalents."))
    return out
