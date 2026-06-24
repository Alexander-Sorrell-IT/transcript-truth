"""Authority-grounded Cyrillic lexicon checks (Russian / Ukrainian).

Grounded in OpenCorpora via pymorphy3 (is_known + POS) and wordfreq (frequency),
so unlike the LLM-built es surfacer this is checkable against a real morphological
dictionary. A factory binds the analyzer to a language so the same logic serves
`ru`, `uk` (and any pymorphy3 language).

`unknown_word` is REVIEW-tier on purpose: an out-of-lexicon token is usually a
proper name (valid) — so we surface it for the human, we don't tank the grade.
The hard, authority-free error stays in cyrillic_rules.mixed_script (homoglyphs).
"""
from __future__ import annotations
import os, json, re, functools
from .types import Flag, Transcript

_CYR_WORD = re.compile(r"[Ѐ-ӿ][Ѐ-ӿ’'\-]*")
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@functools.lru_cache(maxsize=4)
def _analyzer(lang: str):
    import pymorphy3
    return pymorphy3.MorphAnalyzer(lang=lang)


def make_unknown_word(lang: str, min_zipf: float = 1.5):
    """Return a scanner that surfaces Cyrillic tokens absent from the lexicon AND
    rare per wordfreq (so real-but-missing common words don't false-fire)."""
    def unknown_word(t: Transcript) -> list[Flag]:
        from wordfreq import zipf_frequency
        ana = _analyzer(lang)
        out = []
        for ln in t.lines:
            for m in _CYR_WORD.finditer(ln.text):
                w = m.group(0)
                if len(w) < 3:
                    continue
                if ana.parse(w)[0].is_known:
                    continue
                if zipf_frequency(w, lang) >= min_zipf:
                    continue  # real word the dict just lacks
                likely_name = w[:1].isupper()
                out.append(Flag(
                    rule=f"{lang}_unknown_word", severity="review", line=ln.n, evidence=w,
                    label=(f"out-of-lexicon {lang.upper()} word '{w}'"
                           + (" — likely a proper name, verify" if likely_name
                              else " — not in dictionary, check spelling")),
                    fix="Confirm against the audio; keep if a real name/term, else correct the spelling."))
        return out
    unknown_word.__name__ = f"{lang}_unknown_word"
    return unknown_word


@functools.lru_cache(maxsize=4)
def _confusables(lang: str):
    """Load data/{lang}_confirmed.json -> (single-word index, multiword list).
    Built by the ru-uk-confusables workflow, then grounded against pymorphy3."""
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


def make_confusables(lang: str):
    """Surface any confirmed-confusable member word for human review (the es_rules
    analog for Cyrillic). REVIEW-tier + OPT-IN: like the Spanish surfacer it fires on
    correct lines too (paronyms are real common words), so it never enters the graded
    base profile — it's for a transcriber who wants every trap flagged to check vs audio."""
    _W = re.compile(r"[Ѐ-ӿ]+")
    def confusables(t: Transcript) -> list[Flag]:
        single, multi = _confusables(lang)
        out = []
        for ln in t.lines:
            low = ln.text.lower()
            hits = {}
            for m in _W.finditer(ln.text):
                e = single.get(m.group(0).lower())
                if e and id(e) not in hits:
                    hits[id(e)] = (m.group(0), e)
            for w, e in multi:
                if id(e) not in hits and re.search(r"\b" + re.escape(w) + r"\b", low):
                    hits[id(e)] = (w, e)
            for surf, e in hits.values():
                alts = " / ".join(f"{o['word']} = {o.get('gloss','')}" for o in e["options"])
                out.append(Flag(
                    rule=f"{lang}_confusable", severity="review", line=ln.n, evidence=surf,
                    label=f"{lang.upper()} confusable: '{surf}' ({e.get('trap_type','')}) — confirm by meaning",
                    fix=(e.get("note") or f"Pick by context: {alts}")[:300]))
        return out
    confusables.__name__ = f"{lang}_confusable"
    return confusables
