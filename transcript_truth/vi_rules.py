"""Vietnamese deterministic rule. The Vietnamese alphabet has NO f, j, w, or z — a native
Vietnamese syllable never contains them, so a word with f/j/w/z is a loanword, abbreviation, name,
or a mishearing to verify. Deterministic, line-cited, model-free (mirrors the Turkish q/w/x check).
The Latin authority lexicon check (wordfreq, since pyspellchecker lacks vi) is wired in profiles/vi.py.
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

# a word containing f/j/w/z (the four letters absent from the Vietnamese alphabet)
_FOREIGN = re.compile(r"\b[^\W\d_]*[fjwzFJWZ][^\W\d_]*\b", re.UNICODE)


def vietnamese_foreign_letters(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _FOREIGN.finditer(ln.text):
            w = m.group(0)
            if len(w) < 2:
                continue
            out.append(Flag(
                rule="vi_foreign_letter", label=f"'{w}' contains f/j/w/z — not in the Vietnamese alphabet",
                line=ln.n, severity="review", evidence=w,
                fix="Vietnamese has no f/j/w/z — verify: keep if a foreign name/term, else correct."))
    return out
