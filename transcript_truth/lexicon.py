"""Generic authority-dictionary (known-word) check across languages.

One interface, three backends, picked per language:
  - ru/uk -> pymorphy3 / OpenCorpora (morphological: knows inflected forms)
  - en/es/... -> pyspellchecker (wordlist)
  - fallback -> wordfreq (frequency > 0)

Gives es/en the same out-of-lexicon surfacer ru/uk already have, so the
`unknown_word` capability is uniform. REVIEW-tier (an unknown token is often a
proper name), exactly like the Cyrillic version.
"""
from __future__ import annotations
import functools, re
from .types import Flag, Transcript

_WORD = {
    "cyrillic": re.compile(r"[Ѐ-ӿ][Ѐ-ӿ’'\-]*"),
    "latin": re.compile(r"[^\W\d_]{2,}", re.UNICODE),
}


@functools.lru_cache(maxsize=8)
def _backend(lang: str):
    if lang in ("ru", "uk"):
        import pymorphy3
        return ("pymorphy", pymorphy3.MorphAnalyzer(lang=lang))
    try:
        from spellchecker import SpellChecker
        return ("spell", SpellChecker(language=lang))
    except Exception:
        return ("freq", None)


def is_known(word: str, lang: str) -> bool:
    kind, obj = _backend(lang)
    if kind == "pymorphy":
        return obj.parse(word)[0].is_known
    if kind == "spell":
        return word.lower() in obj
    from wordfreq import zipf_frequency
    return zipf_frequency(word.lower(), lang) > 0


def make_unknown_word(lang: str, script: str = "latin", min_zipf: float = 3.0):
    """Surfacer: flag tokens absent from the lexicon AND below the frequency escape.
    min_zipf=3.0 is calibrated so common misspellings (zipf<3) stay flagged while
    real-but-rare words / inflections the dict lacks (zipf>=3) are spared."""
    rx = _WORD["cyrillic"] if script == "cyrillic" else _WORD["latin"]

    def unknown_word(t: Transcript) -> list[Flag]:
        from wordfreq import zipf_frequency
        out = []
        for ln in t.lines:
            for m in rx.finditer(ln.text):
                w = m.group(0)
                if len(w) < 3 or is_known(w, lang):
                    continue
                if zipf_frequency(w.lower(), lang) >= min_zipf:
                    continue
                out.append(Flag(
                    rule=f"{lang}_unknown_word", severity="review", line=ln.n, evidence=w,
                    label=f"out-of-lexicon {lang.upper()} word '{w}' — verify spelling/name",
                    fix="Confirm against the audio; keep if a real name/term, else correct."))
        return out
    unknown_word.__name__ = f"{lang}_unknown_word"
    return unknown_word
