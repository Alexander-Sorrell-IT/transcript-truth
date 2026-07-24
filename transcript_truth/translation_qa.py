"""Per-language translation-QA layer (ROADMAP Phase 8 task 4).

Self-contained, deterministic, language-agnostic CORE checks over a (source, translation)
pair — the SAME verdict philosophy as the rest of the engine: mechanical rules own the
verdict, and a check that cannot be performed reports ``verifiable=False`` rather than
faking a green.  Zero false positives on correct text matters more than catching everything.

Three checks (no model anywhere in the verdict path):
  (1) LENGTH-RATIO sanity — a translation grossly shorter (truncation) or longer (padding /
      untranslated echo) than the source's expected span for that language pair.  Bands are
      per-pair and deliberately TOLERANT; when the pair's expected ratio is unknown the check
      reports unverifiable instead of guessing.
  (2) SOURCE-SCRIPT LEAK — untranslated native-script runs (Arabic / Devanagari / CJK /
      Cyrillic / Hebrew / Hangul / Thai / Greek) still sitting in a Latin-script translation
      are an untranslated segment; flagged with the offending substring.
  (3) GLOSSARY adherence — a per-language-pair registry (``register_translation_layer``) can
      force a required target rendering: when a registered source term appears in the source
      and its mandated target rendering is absent from the translation, that is a violation.

This module imports NOTHING from the rest of the package (stdlib ``re`` + ``unicodedata``
only) so it loads on its own and never races a parallel edit of translate.py.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Placeholders / inline tags that a CAT-tool / MTPE job (Smartcat, Unbabel, agency TMs) requires to
# survive translation VERBATIM — the #1 reason MTPE work is rejected. Conservative patterns chosen to
# not false-fire on prose: "50% of" / "a < b" / "<3" never match (a format letter or tag-name must
# follow immediately).
_PLACEHOLDER = re.compile(
    r"\{\{?\s*[\w.$-]+\s*\}?\}"                  # {name} {{count}} {order.id} { x }
    r"|%\(\w+\)[sdf]"                            # %(name)s  (python named)
    r"|%(?:\d+\$)?[sdf]"                         # %s %d %f %1$s  (printf, tight)
    r"|\[\d+\]"                                  # [1]  numbered CAT tag
    r"|</?[a-zA-Z][\w:-]*(?:\s[^<>]*?)?/?>"      # <g id="1"> </g> <x/>  (well-formed tags only)
)


def _placeholders(text: str) -> Counter:
    return Counter(m.group(0) for m in _PLACEHOLDER.finditer(text or ""))

# --------------------------------------------------------------------------------------------
# script / language classification
# --------------------------------------------------------------------------------------------

# language code -> writing system (anything absent is assumed Latin script)
_SCRIPT_BY_LANG = {
    "ar": "arabic", "fa": "arabic", "ur": "arabic", "ps": "arabic", "sd": "arabic",
    "he": "hebrew", "yi": "hebrew",
    "hi": "devanagari", "mr": "devanagari", "ne": "devanagari", "sa": "devanagari",
    "bn": "bengali", "as": "bengali",
    "ru": "cyrillic", "uk": "cyrillic", "bg": "cyrillic", "sr": "cyrillic",
    "mk": "cyrillic", "be": "cyrillic", "kk": "cyrillic", "mn": "cyrillic",
    "el": "greek",
    "ja": "japanese", "zh": "han", "ko": "hangul", "th": "thai",
    "ta": "tamil", "te": "telugu", "kn": "kannada", "ml": "malayalam",
}


def _base_lang(code: str | None) -> str:
    """Strip region/script subtags: 'en-US' -> 'en', 'zh-Hans' -> 'zh', None -> 'und'."""
    if not code:
        return "und"
    return code.strip().lower().split("-")[0].split("_")[0]


def _script_of(lang: str | None) -> str:
    return _SCRIPT_BY_LANG.get(_base_lang(lang), "latin")


def _is_latin_lang(lang: str | None) -> bool:
    return _script_of(lang) == "latin"


# Contiguous runs of NON-Latin script letters that would be a leak inside a Latin translation.
# Covers Cyrillic, Greek, Hebrew, Arabic (+ supplements), Devanagari/Bengali/Tamil/Telugu/
# Kannada/Malayalam, Thai, Hiragana/Katakana, CJK ideographs (+ ext-A + compat), Hangul.
_FOREIGN_RUN = re.compile(
    "[Ͱ-ϿЀ-ԯԱ-֏֐-׿؀-ۿݐ-ݿ"
    "ࢠ-ࣿऀ-ॿঀ-৿஀-௿ఀ-౿ಀ-೿"
    "ഀ-ൿ฀-๿぀-ヿ㐀-䶿一-鿿가-힯"
    "豈-﫿]+"
)

# --------------------------------------------------------------------------------------------
# length-ratio bands  (target character-span / source character-span, whitespace removed)
# --------------------------------------------------------------------------------------------
# Deliberately WIDE — the goal is to catch gross truncation/padding, never to nitpick a
# faithful paraphrase.  Keyed by SOURCE writing system when translating INTO a Latin target
# (the X->EN production direction).  Non-Latin targets have no band => unverifiable (honest).
_BANDS_TO_LATIN = {
    "latin": (0.50, 1.90),        # es/fr/de/pt... -> en : comparable spans
    "cyrillic": (0.45, 1.95),
    "greek": (0.50, 1.90),
    "arabic": (0.50, 2.40),       # vowel-less script -> longer English
    "hebrew": (0.50, 2.40),
    "devanagari": (0.45, 2.00),
    "bengali": (0.45, 2.00),
    "tamil": (0.45, 2.10),
    "telugu": (0.45, 2.10),
    "kannada": (0.45, 2.10),
    "malayalam": (0.45, 2.10),
    "thai": (0.50, 2.70),
    "hangul": (0.60, 3.40),
    "han": (0.70, 5.80),          # dense ideographs -> much longer English (lower bound relaxed:
    "japanese": (0.60, 5.00),     # a terse-but-faithful English rendering can be short; length is
}                                 # only a SOFT signal now and never sets ok=False)


def _ratio_band(src_lang: str | None, tgt_lang: str | None):
    """(low, high) expected char-span band for the pair, or None when unknown."""
    if not _is_latin_lang(tgt_lang):
        return None                                   # no band defined for non-Latin targets
    return _BANDS_TO_LATIN.get(_script_of(src_lang))


def _span(text: str) -> int:
    """Non-whitespace character count — a script-agnostic length proxy."""
    return sum(1 for c in text if not c.isspace())


# --------------------------------------------------------------------------------------------
# glossary registry
# --------------------------------------------------------------------------------------------
# { "src-tgt" : { source_trigger_term : required_target_rendering } }
_GLOSSARY: dict[str, dict[str, str]] = {}


def _pair_key(lang_pair) -> str:
    """Normalize a language pair to 'src-tgt' with region subtags stripped.

    Accepts a ('es','en') tuple/list or an 'es-en' / 'es_en' / 'es->en' string."""
    if isinstance(lang_pair, (tuple, list)):
        if len(lang_pair) != 2:
            raise ValueError("lang_pair sequence must be (src, tgt)")
        src, tgt = lang_pair
    else:
        parts = re.split(r"->|[-_/|]", str(lang_pair))
        parts = [p for p in parts if p]
        if len(parts) < 2:
            raise ValueError(f"cannot parse lang_pair {lang_pair!r}; use 'src-tgt' or (src, tgt)")
        src, tgt = parts[0], parts[1]
    return f"{_base_lang(src)}-{_base_lang(tgt)}"


def register_translation_layer(lang_pair, terms: dict) -> None:
    """Register (or extend) the glossary for a language pair.

    ``lang_pair`` — 'es-en' or ('es','en') (region subtags are stripped).
    ``terms``     — {source_term: required_target_rendering}.  When ``source_term`` occurs in
                    the source, ``required_target_rendering`` MUST occur in the translation.
    Repeated calls MERGE (later keys win)."""
    if not isinstance(terms, dict):
        raise TypeError("terms must be a {source_term: target_term} dict")
    key = _pair_key(lang_pair)
    layer = _GLOSSARY.setdefault(key, {})
    for s, t in terms.items():
        layer[str(s)] = str(t)


def registered_layers() -> dict:
    """Read-only snapshot of the glossary registry (for tests / receipts)."""
    return {k: dict(v) for k, v in _GLOSSARY.items()}


def clear_translation_layers() -> None:
    """Drop all registered glossary layers (test hygiene)."""
    _GLOSSARY.clear()


# --------------------------------------------------------------------------------------------
# the verdict
# --------------------------------------------------------------------------------------------

def _contains_word(haystack: str, needle: str) -> bool:
    """Boundary-aware, case-insensitive containment. A wordish term must match on token
    boundaries (so a glossary term 'EU' does not fire inside 'Europe' or 'queue'); a term with
    no word characters falls back to plain substring. Fixes the naive-substring glossary FP."""
    n = (needle or "").strip()
    if not n:
        return False
    if re.search(r"\w", n, re.UNICODE):
        return re.search(rf"(?<!\w){re.escape(n)}(?!\w)", haystack,
                         re.IGNORECASE | re.UNICODE) is not None
    return n.lower() in haystack.lower()


_PARENTHETICAL = re.compile(r"\([^)]*\)|\[[^\]]*\]")   # citation of the original — allowed
_WORD = re.compile(r"\w+", re.UNICODE)
_PASSTHROUGH_FLOOR = 0.70   # >= this fraction of source words echoed verbatim = untranslated


def run_qa(source_text: str, translation: str,
           src_lang: str = "en", tgt_lang: str = "en") -> dict:
    """Deterministic per-language translation QA over a (source, translation) pair.

    Returns::

        {"ok": bool,           # deterministic pass: zero flags AND verifiable.  Meaningful
                               #   only when verifiable is True (never a silent green).
         "verifiable": bool,   # could the core checks be mechanically performed?  False =>
                               #   unknown pair or non-Latin target => ok is False (honest).
         "flags": [            # one dict per rule hit, MOST-SEVERE FIRST; [] == clean
             {"kind": str,       # "source_script_leak" | "glossary" | "length_ratio"
              "evidence": str,   # the offending / missing substring
              "note": str}],     # human explanation
         "ratio": float}       # target span / source span (0.0 when source is empty)
    """
    source_text = source_text or ""
    translation = translation or ""
    src_span, tgt_span = _span(source_text), _span(translation)
    ratio = round(tgt_span / src_span, 3) if src_span else 0.0

    flags: list[dict] = []

    # (2) SOURCE-SCRIPT LEAK — most severe: an outright untranslated segment. Only meaningful
    # when the target is Latin-script (a native run in a non-Latin target is correct output).
    # A native-script run INSIDE a parenthetical/bracket is the standard citation-of-the-original
    # convention ("the newspaper Pravda (Газета Правда)") and is NOT a leak — strip those first.
    target_latin = _is_latin_lang(tgt_lang)
    if target_latin:
        body = _PARENTHETICAL.sub(" ", translation)
        seen = set()
        for m in _FOREIGN_RUN.finditer(body):
            run = m.group(0).strip()
            if not run or run in seen:
                continue
            seen.add(run)
            flags.append({
                "kind": "source_script_leak",
                "evidence": run,
                "note": (f"untranslated source-script run left in a {_base_lang(tgt_lang)} "
                         f"translation"),
            })

    # (2b) SAME-SCRIPT PASSTHROUGH — when source and target share a writing system (es->en,
    # ru->uk), a source-script leak is invisible, so a verbatim/near-verbatim echo of the source
    # would otherwise pass as a silent green. Catch it: a HIGH fraction of source words appearing
    # unchanged in the translation means it was not really translated. High floor + content is
    # mostly function words that differ across languages, so FP on a genuine translation is
    # negligible; the failure mode this closes (untranslated passthrough) is a hard flag.
    passthrough_checkable = (_base_lang(src_lang) != _base_lang(tgt_lang)
                             and _script_of(src_lang) == _script_of(tgt_lang))
    if passthrough_checkable:
        src_toks = _WORD.findall(source_text.lower())
        tgt_set = set(_WORD.findall(translation.lower()))
        if src_toks:
            kept = sum(1 for w in src_toks if w in tgt_set) / len(src_toks)
            if kept >= _PASSTHROUGH_FLOOR:
                flags.append({
                    "kind": "untranslated_passthrough",
                    "evidence": f"{kept:.0%} of source words unchanged",
                    "note": (f"{_base_lang(src_lang)} and {_base_lang(tgt_lang)} share a script "
                             f"and {kept:.0%} of source words survive verbatim — the text appears "
                             f"untranslated"),
                })

    # (3) GLOSSARY adherence — a registered source term must reach its mandated rendering.
    # Word-boundary match so 'EU' does not fire inside 'Europe'.
    layer = _GLOSSARY.get(f"{_base_lang(src_lang)}-{_base_lang(tgt_lang)}", {})
    for src_term, tgt_term in layer.items():
        if _contains_word(source_text, src_term) and not _contains_word(translation, tgt_term):
            flags.append({
                "kind": "glossary",
                "evidence": tgt_term,
                "note": (f"source term {src_term!r} requires rendering {tgt_term!r}, "
                         f"which is absent from the translation"),
            })

    # (4) PLACEHOLDER / TAG SURVIVAL — the CAT-tool / MTPE non-negotiable. Every {var}, %s, [1], or
    # <tag> in the source must appear verbatim in the translation; an introduced one breaks rendering
    # too. Language-neutral, so this is a confident flag in EITHER direction regardless of script.
    src_ph, tgt_ph = _placeholders(source_text), _placeholders(translation)
    for ph in sorted((src_ph - tgt_ph).elements()):
        flags.append({"kind": "placeholder", "evidence": ph,
                      "note": f"placeholder/tag {ph!r} in the source is MISSING from the translation "
                              f"— CAT/MTPE jobs (Smartcat, Unbabel, agency TMs) reject this"})
    for ph in sorted((tgt_ph - src_ph).elements()):
        flags.append({"kind": "placeholder", "evidence": ph,
                      "note": f"placeholder/tag {ph!r} was INTRODUCED in the translation but is not "
                              f"in the source"})

    # (1) LENGTH-RATIO sanity — gross truncation/padding. Only a KNOWN band fires; the dense-script
    # bands (ja/han/hangul/thai) are deliberately WIDE so a terse-but-faithful translation is not
    # false-flagged (the FP the review caught), while a genuine 0.3x truncation still trips.
    band = _ratio_band(src_lang, tgt_lang)
    ratio_verifiable = band is not None and src_span > 0
    if ratio_verifiable:
        low, high = band
        if ratio < low or ratio > high:
            why = "truncation / dropped content" if ratio < low else "padding / untranslated echo"
            flags.append({
                "kind": "length_ratio",
                "evidence": f"{ratio:.2f}",
                "note": (f"translation span is {ratio:.2f}x the source (expected "
                         f"{low:.2f}-{high:.2f}x) — likely {why}"),
            })

    # verifiable: could we mechanically vet clean-looking text?  True when the target is Latin
    # (leak detectable) OR a same-script pair (passthrough detectable). A pair we cannot inspect
    # stays unverifiable so ok is never a silent green.
    verifiable = target_latin or passthrough_checkable
    ok = (not flags) and verifiable

    return {"ok": ok, "verifiable": verifiable, "flags": flags, "ratio": ratio}
