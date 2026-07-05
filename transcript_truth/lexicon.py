"""Generic authority-dictionary (known-word) check across languages.

One interface, four backends, picked per language:
  - ru/uk -> pymorphy3 / OpenCorpora (morphological: knows inflected forms)
  - ko -> mecab-ko-dic (morphological: real words parse into whole dictionary
    morphemes; ASR garble shatters into single-char scraps). wordfreq is USELESS
    for Korean validity: it averages per-syllable frequency, so any hangul string
    scores > 0 (measured: garble '즈끄즈' zipf 4.27 vs real '계좌' 4.44).
  - en/es/... -> pyspellchecker (wordlist)
  - fallback -> wordfreq (frequency > 0)

Gives es/en the same out-of-lexicon surfacer ru/uk already have, so the
`unknown_word` capability is uniform. REVIEW-tier (an unknown token is often a
proper name), exactly like the Cyrillic version.
"""
from __future__ import annotations
import os, json, functools, re
from .types import Flag, Transcript

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_WORD = {
    "cyrillic": re.compile(r"[Ѐ-ӿ][Ѐ-ӿ’'\-]*"),
    "latin": re.compile(r"[^\W\d_]{2,}", re.UNICODE),
}


@functools.lru_cache(maxsize=8)
def _backend(lang: str):
    if lang in ("ru", "uk"):
        import pymorphy3
        return ("pymorphy", pymorphy3.MorphAnalyzer(lang=lang))
    if lang == "ko":
        try:
            import MeCab, mecab_ko_dic
            return ("mecab_ko", MeCab.Tagger(mecab_ko_dic.MECAB_ARGS))
        except Exception:
            return ("freq", None)
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
    if kind == "mecab_ko":
        # known iff most of the word is covered by multi-char dictionary morphemes;
        # garble parses only into 1-char scraps (즈+끄+즈), real words don't (계좌, 그러+면).
        lines = [l for l in obj.parse(word).split("\n") if "\t" in l]
        if not lines:
            return False
        covered = sum(len(l.split("\t")[0]) for l in lines
                      if len(l.split("\t")[0]) >= 2
                      and not l.split("\t")[1].startswith(("UNKNOWN", "UNA", "SY")))
        return len(word) < 2 or covered * 2 >= len(word)
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


@functools.lru_cache(maxsize=8)
def _conf(lang: str):
    """single-word index + multiword list of confusable members from <lang>_confirmed.json."""
    try:
        data = json.load(open(os.path.join(_DATA, f"{lang}_confirmed.json"), encoding="utf-8"))
    except Exception:
        return {}, []
    single, multi = {}, []
    for e in data:
        for o in e.get("options", []):
            w = (o.get("word") or "").strip().lower()
            if not w:
                continue
            if " " in w or "-" in w:
                multi.append((w, e))
            else:
                single.setdefault(w, e)
    return single, multi


def make_confusables(lang: str, script: str = "latin"):
    """Generic confusable surfacer (review, opt-in) — Latin or Cyrillic. Mirrors the
    es/ru surfacers so es/en share one implementation."""
    rx = _WORD["cyrillic"] if script == "cyrillic" else _WORD["latin"]

    def confusables(t: Transcript) -> list[Flag]:
        single, multi = _conf(lang)
        out = []
        for ln in t.lines:
            low = ln.text.lower()
            hits = {}
            for m in rx.finditer(ln.text):
                e = single.get(m.group(0).lower())
                if e and id(e) not in hits:
                    hits[id(e)] = (m.group(0), e)
            for w, e in multi:
                if id(e) not in hits and re.search(r"\b" + re.escape(w) + r"\b", low):
                    hits[id(e)] = (w, e)
            for surf, e in hits.values():
                alts = " / ".join(o.get("word", "") for o in e.get("options", []))
                out.append(Flag(
                    rule=f"{lang}_confusable", severity="review", line=ln.n, evidence=surf,
                    label=f"{lang.upper()} confusable: '{surf}' — confirm by meaning ({alts})",
                    fix=(e.get("note") or f"Pick by context: {alts}")[:300]))
        return out
    confusables.__name__ = f"{lang}_confusable"
    return confusables
