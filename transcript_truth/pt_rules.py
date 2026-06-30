"""Portuguese deterministic rule. The clean mechanical check: a cedilla ç only ever precedes
a, o, u in Portuguese — "çe"/"çi" is ALWAYS wrong (should be plain c, which already sounds soft
before e/i). Fully deterministic, line-cited, model-free. (Latin-lexicon authority check is shared
via lexicon.make_unknown_word, wired in profiles/pt.py.)
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

# ç directly before an e/i vowel (with or without accent) -> always an error.
_CEDILLA_EI = re.compile(r"ç(?=[eiéíêîEIÉÍÊÎ])", re.I)


def portuguese_cedilla(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _CEDILLA_EI.finditer(ln.text):
            ctx = ln.text[max(0, m.start() - 2): m.start() + 3]
            out.append(Flag(
                rule="pt_cedilla", label="Cedilla ç cannot precede e/i in Portuguese",
                line=ln.n, severity="minor", evidence=ctx.strip(),
                fix="Use plain c before e/i (it is already soft): 'çe/çi' -> 'ce/ci'."))
    return out
