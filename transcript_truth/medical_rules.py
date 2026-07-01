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
# trailing zero after a decimal — but only 1–2 fractional digits ("1.0", "2.50"). A 3+-digit group
# ("1.000") is a THOUSANDS separator in de/es/pt/etc. (= 1000), NOT a decimal; flagging it and
# advising "1 mg" would be a 1000x underdose. Capping the fraction keeps this locale-safe.
_TRAILING_ZERO = re.compile(r"\b(\d+\.\d?0)\s*(mg|ml|mcg|g|units?|l)\b", re.I)
_NAKED_DECIMAL = re.compile(r"(?<![\d.])\.(\d+)\s*(mg|ml|mcg|g|units?|l)\b", re.I)


def dangerous_abbreviations(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _TOKEN.finditer(ln.text):
            w = m.group(0)
            # tolerate periods anywhere: trailing (QD.) and interior (q.d. -> qd)
            info = _DO_NOT_USE.get(w) or _DO_NOT_USE.get(w.strip(".")) or _DO_NOT_USE.get(w.replace(".", ""))
            if info:
                w = next((c for c in (w, w.strip("."), w.replace(".", "")) if c in _DO_NOT_USE), w)
                meaning, why = info
                out.append(Flag(
                    rule="med_dangerous_abbrev", severity="moderate", line=ln.n, evidence=w,
                    label=f"Dangerous abbreviation '{w}' ({why}) — write '{meaning}'",
                    fix=f"ISMP 'Do Not Use': spell out '{w}' as '{meaning}'."))
    return out


# a word sitting immediately before a dose (WORD 500 mg) is probably a drug name
_DRUG_CTX = re.compile(r"\b([A-Za-z][A-Za-z\-]{3,})\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|units?|iu)\b", re.I)


def drug_name_check(t: Transcript) -> list[Flag]:
    """Flag a word in DOSAGE position that isn't a known RxNorm drug (and suggest the closest real
    one). Skips common English words (a high wordfreq = a verb like 'gave/took', not a drug).
    No-ops until the drug list is downloaded via `--refresh-data` (medical_data.refresh_drugs)."""
    from .medical_data import drug_set
    drugs = drug_set()
    if not drugs:
        return []
    import difflib
    try:
        from wordfreq import zipf_frequency
    except Exception:
        zipf_frequency = lambda w, l: 0.0
    out: list[Flag] = []
    for ln in t.lines:
        for m in _DRUG_CTX.finditer(ln.text):
            w = m.group(1)
            wl = w.lower()
            if wl in drugs or zipf_frequency(wl, "en") >= 3.3:   # known drug, or a common English word
                continue
            near = difflib.get_close_matches(wl, drugs, n=1, cutoff=0.85)
            sugg = f" — did you mean '{near[0]}'?" if near else ""
            out.append(Flag(
                rule="med_drug_name", severity="review", line=ln.n, evidence=w,
                label=f"'{w}' before a dose isn't a known drug name{sugg}",
                fix="Verify the drug name against the prescription/audio (RxNorm has no match)."))
    return out


def dosage_hygiene(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _TRAILING_ZERO.finditer(ln.text):
            out.append(Flag(
                rule="med_dosage", severity="moderate", line=ln.n, evidence=m.group(0).strip(),
                label=f"Trailing zero '{m.group(0).strip()}' — drop it (a missed decimal = 10x overdose)",
                fix=f"Write '{m.group(1).rstrip('0').rstrip('.')} {m.group(2)}' — never a trailing zero after a decimal."))
        for m in _NAKED_DECIMAL.finditer(ln.text):
            out.append(Flag(
                rule="med_dosage", severity="moderate", line=ln.n, evidence=m.group(0).strip(),
                label=f"Naked decimal '{m.group(0).strip()}' — add a leading zero",
                fix=f"Write '0.{m.group(1)} {m.group(2)}' — always a leading zero before a decimal."))
    return out
