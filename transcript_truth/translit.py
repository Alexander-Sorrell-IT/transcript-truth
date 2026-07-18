"""Non-Latin-script proper-NAME survival (ROADMAP Phase 8) — the deterministic bridge that lets
a name written in Arabic / Devanagari / Kana in the SOURCE be checked against a Latin translation.

The engine's ironclad law governs every decision here: a check that cannot be run RELIABLY
reports verifiable=False and NEVER fakes a pass; and ZERO false positives on a correct translation
matters more than catching every drop. Both pull the same way — be conservative.

WHY THIS IS HARD (measured 2026-07-17, kept as the rationale for the conservative gate):

  * A romanizer is not enough. Arabic script is vowel-less, so camel_tools (ar2bw) and unidecode
    both collapse a name to a consonant SKELETON — 'محمد' -> 'mHmd', 'القاهرة' -> 'AlqAhrp'. Exact
    containment against the vowelized English ('Muhammad', 'Cairo') can never match, so the
    comparator MUST be a consonant-skeleton fuzzy match, not `_name_survives`' exact fold.

  * Even with a fuzzy comparator, IDENTIFYING which source tokens are names is the real blocker.
    adjudicate._name_in_gazetteer fires True on Arabic/Hindi FUNCTION words (سافر, في, من, كان,
    قال, और, के, में, है) because their short skeletons collide with the 2.6M-entry gazetteer,
    and wordfreq cannot gate them out — محمد is zipf 6.11, HIGHER than سافر at 4.23. So a
    source-side extractor built on gazetteer+frequency alone would put common words in the demanded
    set and mass-false-flag correct translations. That violates the zero-FP law.

  * Japanese Han via unidecode is read as CHINESE pinyin ('田中' -> 'Tian Zhong', not 'Tanaka') —
    confidently wrong. The correct lib, pykakasi, is NOT installed. Hindi's indic_transliteration
    is NOT installed either, and unidecode Devanagari diverges on names/places ('मुंबई' -> 'muNbii'
    vs 'Mumbai').

CONCLUSION: name-survival is claimed VERIFIABLE for a source language only when we have BOTH a
faithful per-script romanizer AND a trustworthy deterministic name-identifier for it. With the
libraries currently installed that set is empty (ar/ur: romanizer yes, identifier no; ja/hi:
romanizer absent), so this module honestly reports verifiable=False for every non-Latin source in
production — it is NOT a fake green, it is "the cross-witness agreement control owns this until a
reliable pair lands." The machinery (romanizer registry, skeleton matcher, identifier hooks) is
complete and unit-tested, so the moment pykakasi lands (ja gains a reliable identifier via the
JMnedict name index) or indic lands, the language flips on by data, not by a code change here.
"""
from __future__ import annotations
import re
import unicodedata

# Curated switch: source languages for which we TRUST name identification enough to claim the
# name-survival check verifiable. A language only actually flips on if it is also here AND a
# faithful romanizer is importable (see `_reliable`). Deliberately EMPTY under the current install
# — see the module docstring for the per-language reason. Add a code here ONLY together with a
# reliable romanizer + identifier; never to chase recall.
NAME_VERIFIABLE_LANGS: set[str] = set()


def _strip_accents(s: str) -> str:
    """Diacritic-fold to bare ASCII-ish lowercase (mirrors translate._strip_accents so the two
    sides of a comparison normalize identically)."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if not unicodedata.combining(c)).replace("ø", "o").replace("ß", "ss")


_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")
_VOWELS = re.compile(r"[aeiou]")
_WORD = re.compile(r"[^\s]+")


def _skeleton(s: str) -> str:
    """Consonant skeleton of a romanized token: diacritic-fold, drop non-letters, collapse
    repeated letters, drop vowels. This is what makes a vowel-less Arabic romanization comparable
    to a vowelized English spelling:
        'Muhammad' -> 'mhmd'      'mHmd' (ar2bw) -> 'mhmd'      -> equal
        'Rajesh'   -> 'rjsh'      'raajesh' (uni) -> 'rjsh'     -> equal
    """
    s = _strip_accents(s)
    s = re.sub(r"[^a-z]", "", s)
    s = re.sub(r"(.)\1+", r"\1", s)          # collapse runs (mm -> m) BEFORE dropping vowels
    return _VOWELS.sub("", s)


def _ratio(a: str, b: str) -> float:
    import difflib
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def _skeleton_match(romanized_name: str, translation: str) -> bool:
    """High-precision test: does the romanized source name survive (by consonant skeleton) as a
    whole word in the Latin translation? Exact skeleton equality, or — only for skeletons of
    length >= 3, to keep short skeletons from colliding — a >= 0.86 fuzzy ratio to absorb
    transliteration spelling drift. A too-short (< 2) skeleton is treated as unmatchable rather
    than risk a false match."""
    want = _skeleton(romanized_name)
    if len(want) < 2:
        return False
    for m in _WORD.finditer(translation):
        got = _skeleton(m.group(0))
        if not got:
            continue
        if got == want:
            return True
        if len(want) >= 3 and len(got) >= 3 and _ratio(want, got) >= 0.86:
            return True
    return False


# ---- per-script romanizers: faithful lib per the design, else None (never a wrong-lib guess) ----

_ROMANIZER_CACHE: dict[str, object] = {}


def _romanizer(lang: str):
    """Return a callable native-str -> Latin-str for `lang` using the script-appropriate library
    the design designates, or None when that library is not installed. We do NOT fall back to
    unidecode for ja/hi in production: unidecode reads Japanese Han as Chinese and diverges on
    Devanagari, which would be confidently wrong, not merely absent."""
    lang = (lang or "").split("-")[0]
    if lang in _ROMANIZER_CACHE:
        return _ROMANIZER_CACHE[lang]
    fn = None
    if lang in ("ar", "ur"):
        try:
            from camel_tools.utils.charmap import CharMapper
            _m = CharMapper.builtin_mapper("ar2bw")
            fn = lambda s, _m=_m: _m(s)
        except Exception:
            fn = None
    elif lang in ("ja", "jp"):
        try:
            import pykakasi
            _k = pykakasi.kakasi()
            fn = lambda s, _k=_k: " ".join(it.get("hepburn", "") for it in _k.convert(s))
        except Exception:
            fn = None
    elif lang == "hi":
        try:
            from indic_transliteration import sanscript
            fn = lambda s: sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.IAST)
        except Exception:
            fn = None
    _ROMANIZER_CACHE[lang] = fn
    return fn


def _gazetteer_identifier(lang: str):
    """Generic fallback name-identifier: native token -> bool, backed by the cross-script gazetteer
    bridge with its OWN frequency floor (NOT adjudicate._is_word, which drops 'muhammad' as a
    common word and would silently vanish real names). CAUTION: for ar/hi this is unreliable
    (function words collide in the gazetteer, frequency can't separate names) — it is used only for
    languages placed in NAME_VERIFIABLE_LANGS, and none currently are. Returns None if the
    gazetteer is unavailable."""
    try:
        from .adjudicate import _name_in_gazetteer
    except Exception:
        return None

    def ident(tok: str) -> bool:
        w = tok.strip().lower()
        if not w or _LATIN_LETTER.search(tok):     # native-script tokens only
            return False
        if not _name_in_gazetteer(w):
            return False
        try:
            from wordfreq import zipf_frequency
            # a proper name that is ALSO an everyday function word is ambiguous -> don't demand it.
            # (this floor is the extractor's OWN, not reused from _latin_names.)
            if zipf_frequency(w, lang) >= 5.5:
                return False
        except Exception:
            pass
        return True
    return ident


def _identifier(lang: str):
    """Return a TRUSTWORTHY native-token -> bool name-identifier for `lang`, or None. Prefers a
    language-native authoritative index (Japanese: JMnedict via verdict.name_index) over the
    generic gazetteer fallback."""
    lang = (lang or "").split("-")[0]
    if lang in ("ja", "jp"):
        try:
            from .verdict import name_index
            idx = name_index()
            return lambda tok, _i=idx: tok.strip() in _i
        except Exception:
            return None
    return _gazetteer_identifier(lang)


def _target_is_latin(translation: str) -> bool:
    """A romanized source name can only be matched against a Latin-script translation. If the
    target itself is non-Latin, the comparison is meaningless -> caller must report verifiable=False
    rather than guess."""
    letters = [c for c in translation if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if c.isascii() or _strip_accents(c).isascii())
    return latin >= 0.8 * len(letters)


def _reliable(lang: str) -> bool:
    """The single honest gate: name-survival is verifiable for `lang` ONLY with a faithful
    romanizer AND a trustworthy identifier AND the language explicitly whitelisted."""
    lang = (lang or "").split("-")[0]
    return (lang in NAME_VERIFIABLE_LANGS
            and _romanizer(lang) is not None
            and _identifier(lang) is not None)


def name_survival_translit(source_text: str, translation: str,
                           src_lang: str, tgt_lang: str = "en") -> dict:
    """Transliteration-based proper-name survival for a non-Latin source.

    Returns {"missing_names": [...], "verifiable": bool, "checked": [...]}:
      * verifiable=False  => could NOT be reliably checked (no faithful romanizer+identifier for
        this language, or a non-Latin target). missing_names is [] — NEVER a fake pass; the caller
        surfaces the uncertainty.
      * verifiable=True   => every gazetteer/identifier-confirmed source name was romanized and
        its consonant skeleton matched (or not) against the translation. missing_names lists the
        romanized names that did NOT survive; checked lists every name that was demanded.
    """
    if not _reliable(src_lang) or not _target_is_latin(translation):
        return {"missing_names": [], "verifiable": False, "checked": []}

    romanize = _romanizer(src_lang)
    is_name = _identifier(src_lang)
    checked: list[str] = []
    missing: list[str] = []
    for m in _WORD.finditer(source_text):
        tok = m.group(0)
        if _LATIN_LETTER.search(tok):            # already-Latin tokens are the Latin path's job
            continue
        try:
            if not is_name(tok):
                continue
            rn = (romanize(tok) or "").strip()
        except Exception:
            continue
        if not rn:
            continue
        checked.append(rn)
        if not _skeleton_match(rn, translation):
            missing.append(rn)
    return {"missing_names": sorted(set(missing)), "verifiable": True,
            "checked": sorted(set(checked))}
