"""English formatting rules from the GoTranscript guideline, as deterministic scanners
(no model). These are the long-tail rules editors penalize: slang->standard, Okay,
yeah->yes, all right, abbreviation periods, () vs [], spelled large numbers.
"""
import re
from .types import Flag, Transcript

# slang -> standard form (clean verbatim). Contractions (ain't, y'all, don't) are KEPT.
_SLANG = {
    "gonna": "going to", "wanna": "want to", "gotta": "got to", "gotcha": "got you",
    "kinda": "kind of", "sorta": "sort of", "betcha": "bet you", "dunno": "don't know",
    "lemme": "let me", "gimme": "give me", "cuz": "because", "cause": "because",
    "outta": "out of", "hafta": "have to", "coulda": "could have", "shoulda": "should have",
    "woulda": "would have", "ya": "you",
}
_YES = {"yeah", "yep", "yup", "yap"}


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


def en_format(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        x = ln.text
        # slang -> standard
        for s, std in _SLANG.items():
            if re.search(rf"\b{s}\b", x, re.I):
                out.append(_flag("slang", f"'{s}' should be standard form '{std}'", ln.n, s,
                                 f"Clean verbatim: write '{std}', not '{s}'."))
        # yeah/yep/yup -> yes
        for y in _YES:
            if re.search(rf"\b{y}\b", x, re.I):
                out.append(_flag("slang", f"'{y}' should be written as 'yes'", ln.n, y,
                                 "Affirmatives yeah/yep/yup are written as 'yes'."))
        # OK / Ok -> Okay
        for m in re.finditer(r"\b(OK|Ok|okay)\b", x):
            if m.group(0) != "Okay":
                out.append(_flag("okay", f"'{m.group(0)}' must be spelled 'Okay'", ln.n, m.group(0),
                                 "Never 'OK'/'Ok'/'okay' — always 'Okay'."))
        # alright -> all right
        if re.search(r"\balright\b", x, re.I):
            out.append(_flag("spelling", "'alright' must be 'all right'", ln.n, "alright",
                             "Write 'all right', not 'alright'."))
        # abbreviation with periods: U.S.A., Ph.D. (but Dr./Mrs. are fine in US English)
        for m in re.finditer(r"\b([A-Z]\.){2,}[A-Z]?\.?", x):
            ab = m.group(0)
            if ab not in ("Dr.", "Mrs.", "Mr.", "Ms.", "Jr.", "Sr."):
                out.append(_flag("abbreviation", f"'{ab}' should drop the periods (e.g. USA, PhD)", ln.n, ab,
                                 "Acronyms have no periods: USA, PhD — not U.S.A., Ph.D."))
        # () used for a sound/inaudible tag -> should be []
        for m in re.finditer(r"\((laughs?|laughter|inaudible|unintelligible|crosstalk|applause|sighs?|coughs?|pause|silence)[^)]*\)", x, re.I):
            out.append(_flag("brackets", f"'{m.group(0)}' must use [ ] not ( )", ln.n, m.group(0),
                             "Sound/inaudible tags use square brackets [ ], never ( )."))
        # English word immediately followed by full-width Japanese punctuation -> English punctuation
        for m in re.finditer(r"[A-Za-z]([。、！])", x):
            out.append(_flag("mixed_punctuation",
                             f"English word followed by full-width '{m.group(1)}' — use English punctuation",
                             ln.n, m.group(0), "In English text use '.'/',' , not 。/、."))
        # spelled-out numbers 10+ -> use numerals (review tier — has readability exceptions)
        for m in re.finditer(r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million)\b", x, re.I):
            out.append(_flag("numbers", f"'{m.group(0)}' (10+) is usually written in numerals", ln.n, m.group(0),
                             "Spell out 0-9; use numerals for 10 and up (exceptions: o'clock, money, years).", "review"))
    return out
