"""Legal terminology reference (the legal 'more resources' layer). Unlike medical (RxNorm is an
authoritative free DB), legal has no single canonical free source, so this is a comprehensive
CURATED map of commonly mis-transcribed legal terms / Latin phrases -> the correct form. Every key
is a genuinely WRONG form (never a real word), so it's high-precision: it only fires on a real error,
no false positives. Latin legal terms are largely language-agnostic, so this lives in the legal DOMAIN.
Grows over time (expandable like a lexicon)."""
from __future__ import annotations
import re
from .types import Flag, Transcript

# wrong form (lowercased) -> correct legal form. Curated; add freely. Keys must be non-words.
_TERMS = {
    # Latin phrases (the most-mis-transcribed)
    "habeus corpus": "habeas corpus", "habeas corpis": "habeas corpus", "habeous corpus": "habeas corpus",
    "voire dire": "voir dire", "vore dire": "voir dire", "vore deer": "voir dire", "war dire": "voir dire",
    "amicus curie": "amicus curiae", "amicus curaie": "amicus curiae", "amicus curii": "amicus curiae",
    "res ipsa loquitor": "res ipsa loquitur", "res ipsa loquito": "res ipsa loquitur",
    "res judicata": "res judicata", "res judicada": "res judicata", "race judicata": "res judicata",
    "stare decises": "stare decisis", "starry decisis": "stare decisis", "stare decisUS": "stare decisis",
    "prima facia": "prima facie", "prima fascia": "prima facie", "prema facie": "prima facie",
    "noll prosequi": "nolle prosequi", "nolo prosequi": "nolle prosequi", "nole prosequi": "nolle prosequi",
    "writ of mandamous": "writ of mandamus", "mandamous": "mandamus",
    "in limit": "in limine", "in lemine": "in limine", "in liminy": "in limine",
    "per curium": "per curiam", "ex party": "ex parte", "ex partay": "ex parte",
    "de fato": "de facto", "de juray": "de jure", "duces tecem": "duces tecum", "duces tecom": "duces tecum",
    "corpus delecti": "corpus delicti", "caveat emptore": "caveat emptor",
    "guardian ad litum": "guardian ad litem", "ad litum": "ad litem",
    "nunc pro tunk": "nunc pro tunc", "certorari": "certiorari", "certiorary": "certiorari",
    "subpena": "subpoena", "subpeona": "subpoena", "supena": "subpoena",
    "subpena duces tecum": "subpoena duces tecum",
    # English legal terms (common misspellings)
    "defendent": "defendant", "defendents": "defendants",
    "plaintif": "plaintiff", "plaintifs": "plaintiffs", "plantiff": "plaintiff", "plantif": "plaintiff",
    "affidavid": "affidavit", "affadavit": "affidavit", "affidavate": "affidavit",
    "deposistion": "deposition", "deposicion": "deposition", "deposistions": "depositions",
    "perjery": "perjury", "purjury": "perjury",
    "indictement": "indictment", "indightment": "indictment", "indicment": "indictment",
    "prosecuter": "prosecutor", "prosecuters": "prosecutors", "prosicutor": "prosecutor",
    "testomony": "testimony", "testiphony": "testimony", "testemony": "testimony",
    "arrainment": "arraignment", "araignment": "arraignment",
    "malfeasence": "malfeasance", "misfeasence": "misfeasance",
    "jurispudence": "jurisprudence", "jurisprudance": "jurisprudence",
    "tortuous interference": "tortious interference",
    "statue of limitations": "statute of limitations", "statue of limitation": "statute of limitations",
    "et all": "et al.", "et cetra": "et cetera", "et setera": "et cetera",
    "writ of certorari": "writ of certiorari",
}
# alternation longest-first so multi-word phrases match before single words
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
