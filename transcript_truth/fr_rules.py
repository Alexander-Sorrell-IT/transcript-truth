"""French deterministic rules. The distinctive mechanical French check is TYPOGRAPHY SPACING:
French puts a (non-breaking) space BEFORE the "high" punctuation ; : ! ? and before the closing
guillemet », and a space AFTER the opening guillemet «. This is the opposite of English and a
frequent transcription slip — fully deterministic, line-cited, no model. (The Latin-lexicon
authority check is shared via lexicon.make_unknown_word, wired in profiles/fr.py.)
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

# A LETTER immediately before ; : ! ? or » -> missing the required French space.
# Anchoring on a letter (not \S) avoids false-firing on times/timestamps ("12:30", "[00:01:02]")
# and numeric ratios, where the char before the colon is a digit.
_NEEDS_SPACE_BEFORE = re.compile(r"[A-Za-zÀ-ÿ]([;:!?»])")
# Opening guillemet not followed by a space.
_NEEDS_SPACE_AFTER = re.compile(r"(«)[^\s]")
_LABEL = "{ ; : ! ? »"  # for the fix message


def french_spacing(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _NEEDS_SPACE_BEFORE.finditer(ln.text):
            p = m.group(1)
            out.append(Flag(
                rule="fr_spacing", label=f"French: a space is required before « {p} »",
                line=ln.n, severity="minor", evidence=m.group(0),
                fix="French typography puts a (non-breaking) space before ; : ! ? and the closing »."))
        for m in _NEEDS_SPACE_AFTER.finditer(ln.text):
            out.append(Flag(
                rule="fr_spacing", label="French: a space is required after the opening « guillemet",
                line=ln.n, severity="minor", evidence=m.group(0),
                fix="French puts a space after the opening guillemet « and before the closing »."))
    return out
