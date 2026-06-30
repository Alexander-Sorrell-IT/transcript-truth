"""Medical DOMAIN rules (language-agnostic — compose with any language).

The crown jewel is the ISMP / Joint Commission "Do Not Use" dangerous-abbreviation list: these
abbreviations cause real medication errors, the list is fixed and public, and detection is 100%
deterministic — exactly the engine's sweet spot, and a SAFETY check, not just style. Plus dosage
hygiene (trailing zero, naked decimal). No model in the verdict path.
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

# abbrev (matched as a whole token, case-sensitive where it matters) -> (meaning, why dangerous)
_DO_NOT_USE = {
    "U": ("units", "mistaken for 0, 4, or cc"),
    "u": ("units", "mistaken for 0, 4, or cc"),
    "IU": ("international units", "mistaken for IV or 10"),
    "QD": ("daily", "mistaken for QID"), "Q.D.": ("daily", "mistaken for QID"),
    "qd": ("daily", "mistaken for QID"),
    "QOD": ("every other day", "mistaken for QD/QID"), "Q.O.D.": ("every other day", "mistaken for QD"),
    "qod": ("every other day", "mistaken for QD"),
    "MS": ("morphine sulfate OR magnesium sulfate", "ambiguous — spell it out"),
    "MSO4": ("morphine sulfate", "mistaken for magnesium sulfate"),
    "MgSO4": ("magnesium sulfate", "mistaken for morphine sulfate"),
    "cc": ("mL", "mistaken for U (units)"),
    "ug": ("mcg", "mistaken for mg (1000x error)"), "µg": ("mcg", "mistaken for mg"),
    "SC": ("subcutaneous", "mistaken for SL"), "SQ": ("subcutaneous", "mistaken for '5 every'"),
    "D/C": ("discharge OR discontinue", "ambiguous — spell it out"),
    "HS": ("at bedtime", "mistaken for half-strength"),
    "TIW": ("3 times a week", "mistaken for 3x/day or twice a week"),
    "AD": ("right ear", "ear/eye abbreviations are mistaken — spell out"),
    "AS": ("left ear", "mistaken — spell out"), "AU": ("both ears", "mistaken — spell out"),
    "OD": ("right eye", "mistaken — spell out"), "OS": ("left eye", "mistaken — spell out"),
    "OU": ("both eyes", "mistaken — spell out"),
}
# Unicode-aware: a token starts with a letter and keeps accented letters whole (so "reçu" is ONE
# token and the single-letter 'u' rule can't fire inside it).
_TOKEN = re.compile(r"[^\W\d_][\w.µ/]*", re.UNICODE)
_TRAILING_ZERO = re.compile(r"\b(\d+)\.0+\s*(mg|ml|mcg|g|units?|l)\b", re.I)
_NAKED_DECIMAL = re.compile(r"(?<![\d.])\.(\d+)\s*(mg|ml|mcg|g|units?|l)\b", re.I)


def dangerous_abbreviations(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _TOKEN.finditer(ln.text):
            w = m.group(0)
            info = _DO_NOT_USE.get(w) or _DO_NOT_USE.get(w.strip("."))   # tolerate a trailing period
            if info:
                w = w.strip(".") if w.strip(".") in _DO_NOT_USE else w
                meaning, why = info
                out.append(Flag(
                    rule="med_dangerous_abbrev", severity="moderate", line=ln.n, evidence=w,
                    label=f"Dangerous abbreviation '{w}' ({why}) — write '{meaning}'",
                    fix=f"ISMP 'Do Not Use': spell out '{w}' as '{meaning}'."))
    return out


def dosage_hygiene(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _TRAILING_ZERO.finditer(ln.text):
            out.append(Flag(
                rule="med_dosage", severity="moderate", line=ln.n, evidence=m.group(0).strip(),
                label=f"Trailing zero '{m.group(0).strip()}' — drop it (a missed decimal = 10x overdose)",
                fix=f"Write '{m.group(1)} {m.group(2)}' — never a trailing zero after a decimal."))
        for m in _NAKED_DECIMAL.finditer(ln.text):
            out.append(Flag(
                rule="med_dosage", severity="moderate", line=ln.n, evidence=m.group(0).strip(),
                label=f"Naked decimal '{m.group(0).strip()}' — add a leading zero",
                fix=f"Write '0.{m.group(1)} {m.group(2)}' — always a leading zero before a decimal."))
    return out
