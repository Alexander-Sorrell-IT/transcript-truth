"""German deterministic rule. The clean mechanical German check is PRE-1996 ß SPELLINGS:
the 1996 orthography reform replaced ß with ss after a short vowel (daß->dass, muß->muss,
läßt->lässt, Schluß->Schluss …). Those old forms are unambiguous and still slip into transcripts
— a high-confidence, line-cited, model-free flag. (Latin-lexicon authority check is shared via
lexicon.make_unknown_word, wired in profiles/de.py.)
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

# Curated set of common pre-reform ß words -> modern ss spelling. Exact stems, high-confidence.
_PRE96 = {
    "daß": "dass", "muß": "muss", "mußt": "musst", "mußte": "musste", "müßte": "müsste",
    "läßt": "lässt", "läßst": "lässt", "gewiß": "gewiss", "schluß": "schluss", "fluß": "fluss",
    "kuß": "kuss", "nuß": "nuss", "paßt": "passt", "faßt": "fasst", "vergißt": "vergisst",
    "naß": "nass", "streß": "stress", "bißchen": "bisschen", "häßlich": "hässlich",
    "roß": "ross", "riß": "riss", "biß": "biss", "wißt": "wisst", "küßt": "küsst",
    "haß": "hass", "paß": "pass", "genuß": "genuss", "schloß": "schloss", "faß": "fass",
    "gefaßt": "gefasst", "beschloß": "beschloss", "mißt": "misst", "iß": "iss",
}
_TOKEN = re.compile(r"[A-Za-zÀ-ÿäöüßÄÖÜ]+")


def german_old_spelling(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _TOKEN.finditer(ln.text):
            w = m.group(0)
            fix = _PRE96.get(w.lower())
            if fix:
                out.append(Flag(
                    rule="de_old_spelling", label=f"Pre-1996 spelling '{w}' — modern German is '{fix}'",
                    line=ln.n, severity="minor", evidence=w,
                    fix=f"The 1996 reform writes ß as ss after a short vowel: '{w}' -> '{fix}'."))
    return out
