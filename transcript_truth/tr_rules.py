"""Turkish deterministic rule. The Turkish alphabet has NO q, w, or x — a native Turkish word
never contains them, so a word with q/w/x is a loanword, a name, or a mishearing to verify.
Deterministic, line-cited, model-free. (Turkish isn't in pyspellchecker, so the lexicon check
degrades to a wordfreq-only frequency escape automatically — see lexicon._backend.)
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

_FOREIGN = re.compile(r"\b[\wçğıöşüÇĞİÖŞÜ]*[qwxQWX][\wçğıöşüÇĞİÖŞÜ]*\b")


def turkish_foreign_letters(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _FOREIGN.finditer(ln.text):
            w = m.group(0)
            out.append(Flag(
                rule="tr_foreign_letter", label=f"'{w}' contains q/w/x — not in the Turkish alphabet",
                line=ln.n, severity="review", evidence=w,
                fix="Turkish has no q/w/x — verify: keep if a foreign name, else correct (q→k, w→v, x→ks)."))
    return out
