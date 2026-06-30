"""Legal terminology reference (the legal 'more resources' layer). Unlike medical (RxNorm is an
authoritative free DB), legal has no single canonical free source, so this is a CURATED map of
commonly mis-transcribed legal terms / Latin phrases -> the correct form. High-precision: it only
fires on a known wrong form, so no false positives. Grows over time (expandable/refreshable like a
lexicon). Latin legal terms are largely language-agnostic, so this lives in the legal DOMAIN."""
from __future__ import annotations
import re
from .types import Flag, Transcript

# wrong form (lowercased) -> correct legal form. Curated; add freely.
_TERMS = {
    "subpena": "subpoena", "subpeona": "subpoena", "subpoena duces tecem": "subpoena duces tecum",
    "habeus corpus": "habeas corpus", "habeas corpis": "habeas corpus",
    "voire dire": "voir dire", "vore dire": "voir dire", "vore deer": "voir dire",
    "amicus curie": "amicus curiae", "amicus curaie": "amicus curiae",
    "defendent": "defendant", "defendents": "defendants",
    "plaintif": "plaintiff", "plaintifs": "plaintiffs",
    "affidavid": "affidavit", "affadavit": "affidavit",
    "perjery": "perjury", "deposistion": "deposition", "deposicion": "deposition",
    "indictement": "indictment", "indightment": "indictment",
    "prosecuter": "prosecutor", "testomony": "testimony", "testiphony": "testimony",
    "et all": "et al.", "et cetra": "et cetera",
    "stare decises": "stare decisis", "res ipsa loquitor": "res ipsa loquitur",
    "pro se litigent": "pro se litigant", "writ of mandamous": "writ of mandamus",
    "noll prosequi": "nolle prosequi", "mens rea" : "mens rea",
    "voir dire": "voir dire",  # correct (sentinel, never flagged)
}
# build alternation longest-first so multi-word phrases match before single words
_PAT = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in _TERMS if _TERMS[k] != k),
                                            key=len, reverse=True)) + r")\b", re.I)


def legal_terms(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _PAT.finditer(ln.text):
            wrong = m.group(1)
            correct = _TERMS[wrong.lower()]
            out.append(Flag(
                rule="legal_term", severity="moderate", line=ln.n, evidence=wrong,
                label=f"Legal term '{wrong}' should be '{correct}'",
                fix=f"Correct legal terminology: '{correct}'."))
    return out
