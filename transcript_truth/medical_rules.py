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
    # audit 2026-07-07 additions (ISMP classes previously missing)
    "QHS": ("nightly at bedtime", "mistaken for qhr (every hour)"),
    "QN": ("nightly", "mistaken for qh (every hour)"),
    "BT": ("bedtime", "mistaken for BID (twice daily)"),
    "SS": ("sliding scale", "mistaken for 55 / SSRI"),
    "UD": ("as directed", "mistaken for unit dose"),
    "IN": ("intranasal", "mistaken for IM or IV"),
    "IT": ("intrathecal", "mistaken for other routes"),
    "OJ": ("orange juice", "mistaken for OD/OS (eye) — drug given in the eye"),
    "HCTZ": ("hydrochlorothiazide", "drug-name abbreviation — misread"),
    "MTX": ("methotrexate", "drug-name abbreviation — misread as mitoxantrone"),
    "AZT": ("zidovudine", "drug-name abbreviation — misread as azathioprine"),
    "CPZ": ("Compazine (prochlorperazine)", "misread as chlorpromazine"),
    "HCT": ("hydrocortisone", "misread as hydrochlorothiazide"),
    "TAC": ("triamcinolone", "misread as tacrolimus"),
    "T3": ("Tylenol with codeine No. 3", "misread as liothyronine"),
    "ZnSO4": ("zinc sulfate", "misread as morphine sulfate"),
    "PER OS": ("by mouth / orally", "'os' is mistaken for left eye (OS)"),
}
# case-insensitive lookup companion: single/double-letter entries stay case-SENSITIVE
# ('u'/'U', OD/AD ...) because lowercase collisions with real words are constant; longer
# abbreviations (qhs, tiw, mso4, hctz) are flagged whatever the case.
_DO_NOT_USE_CI = {k.upper(): v for k, v in _DO_NOT_USE.items() if len(k) >= 3}
# Unicode-aware: a token starts with a letter and keeps accented letters whole (so "reçu" is ONE
# token and the single-letter 'u' rule can't fire inside it).
_TOKEN = re.compile(r"[^\W\d_][\w.µ/]*", re.UNICODE)
# Latin-only runs for the abbreviation lookup: in CJK/Arabic/Devanagari text a Latin abbreviation
# sits flush against native script ("患者はMTX"), so _TOKEN glues them into one unmatchable token.
# ISMP abbreviations are Latin-script by definition — extract the Latin run and look THAT up.
# Accented letters (ç, é, ü…) are included so "reçu" stays one run and 'u' can't fire inside it;
# digits continue a run (MSO4, T3) but can't start one.
_LATIN_RUN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿµ][A-Za-zÀ-ÖØ-öø-ÿµ0-9./]*")
# trailing zero after a decimal — but only 1–2 fractional digits ("1.0", "2.50"). A 3+-digit group
# ("1.000") is a THOUSANDS separator in de/es/pt/etc. (= 1000), NOT a decimal; flagging it and
# advising "1 mg" would be a 1000x underdose. Capping the fraction keeps this locale-safe.
# unit list covers ISMP-relevant units beyond the original 6 (IU, mEq, mmol, %, gtt).
_UNITS = r"(mg|ml|mcg|g|units?|l|iu|meq|mmol|%|gtt)"
_TRAILING_ZERO = re.compile(r"\b(\d+\.\d?0)\s*" + _UNITS + r"\b", re.I)
_NAKED_DECIMAL = re.compile(r"(?<![\d.])\.(\d+)\s*" + _UNITS + r"\b", re.I)
# COMMA-DECIMAL twins — de/fr/es/pt/tr/ru/uk/vi write "1,0 mg" / ",5 mg". The dot-only
# regexes silently no-op there, which left 13 languages with a DEAD dosage check (audit
# 2026-07-07). Same 1-2 fractional-digit cap: "1,500 mg" is a thousands separator in en,
# but after a comma in comma-decimal locales 3 digits IS a decimal — we stay conservative
# and cap at 2 digits, mirroring the dot rules exactly.
_TRAILING_ZERO_C = re.compile(r"\b(\d+,\d?0)\s*" + _UNITS + r"\b", re.I)
_NAKED_DECIMAL_C = re.compile(r"(?<![\d,]),(\d+)\s*" + _UNITS + r"\b", re.I)
# other ISMP hazards, language-neutral: @ in dose context, x3d, huge unseparated doses,
# unit/unit slash (25 units/10 units misread as 1), > < with clinical units
_AT_DOSE = re.compile(r"\d\s*@\s*\d")
_XDAYS = re.compile(r"\b[xX]\s?\d+\s?[dD]\b")
_BIGDOSE = re.compile(r"\b\d{5,}\s*(units?|iu)\b", re.I)
_SLASH_DOSE = re.compile(r"\d+\s*units?\s*/\s*\d+\s*units?\b", re.I)
_GTLT_DOSE = re.compile(r"[<>]\s*\d+\s*(mg|kg|mmol|bpm|%)", re.I)


def dangerous_abbreviations(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _LATIN_RUN.finditer(ln.text):
            w = m.group(0)
            # tolerate periods anywhere: trailing (QD.) and interior (q.d. -> qd)
            info = (_DO_NOT_USE.get(w) or _DO_NOT_USE.get(w.strip(".")) or _DO_NOT_USE.get(w.replace(".", ""))
                    or _DO_NOT_USE_CI.get(w.replace(".", "").upper()))
            if info:
                # short abbreviations (u, cc, OD…) collide with real words in other languages
                # ('u' = tumor in Vietnamese) — outside English they're only trusted in dose
                # context (a digit within ~8 chars: "10 U", "tiêm 10 U insulin"). English keeps
                # firing without context ("Give MS now" is classic dangerous dictation). 3+ letter
                # abbrevs (qhs, MTX, MSO4) are unambiguous shorthand and fire in every language.
                if len(w.replace(".", "")) <= 2 and t.lang != "en":
                    ctx = ln.text[max(0, m.start() - 8):m.end() + 8]
                    if not any(ch.isdigit() for ch in ctx):
                        continue
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
        from wordfreq import zipf_frequency, available_languages
        langs = available_languages()
    except Exception:
        zipf_frequency, langs = (lambda w, l: 0.0), {}
    lang = getattr(t, "lang", "en") or "en"
    freq_lang = lang if lang in langs else "en"          # score frequency in the transcript's language
    out: list[Flag] = []
    for ln in t.lines:
        for m in _DRUG_CTX.finditer(ln.text):
            w = m.group(1)
            wl = w.lower()
            if wl in drugs or zipf_frequency(wl, freq_lang) >= 3.3:   # known drug, or a common word in-lang
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
        for m in _TRAILING_ZERO_C.finditer(ln.text):
            out.append(Flag(
                rule="med_dosage", severity="moderate", line=ln.n, evidence=m.group(0).strip(),
                label=f"Trailing zero '{m.group(0).strip()}' — drop it (a missed decimal = 10x overdose)",
                fix=f"Write '{m.group(1).rstrip('0').rstrip(',')} {m.group(2)}' — never a trailing zero after a decimal."))
        for m in _NAKED_DECIMAL_C.finditer(ln.text):
            out.append(Flag(
                rule="med_dosage", severity="moderate", line=ln.n, evidence=m.group(0).strip(),
                label=f"Naked decimal '{m.group(0).strip()}' — add a leading zero",
                fix=f"Write '0,{m.group(1)} {m.group(2)}' — always a leading zero before a decimal."))
        for rx, lab, fx in (
            (_AT_DOSE, "'@' in a dose/rate — mistaken for '2'", "Write 'at'."),
            (_XDAYS, "'xNd' — 'for N days' vs 'N doses' ambiguity", "Write 'for N days' or 'N doses' in words."),
            (_BIGDOSE, "large dose without separators — misread by a factor of 10", "Use commas: 100,000 units."),
            (_SLASH_DOSE, "unit/unit slash — '/' is misread as '1'", "Write 'X units and Y units' (spell 'and')."),
            (_GTLT_DOSE, "'>' or '<' with a clinical value — mistaken for 7/L", "Write 'greater than'/'less than'."),
        ):
            for m in rx.finditer(ln.text):
                out.append(Flag(rule="med_dosage", severity="moderate", line=ln.n,
                                evidence=m.group(0).strip(), label=lab, fix=fx))
    return out
