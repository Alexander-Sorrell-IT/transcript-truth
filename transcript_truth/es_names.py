"""Spanish proper-name surfacer — the Latin-script analog of the Japanese name
surfacer (jp_name_surfaces.json in verdict.py).

WHY THIS EXISTS: ASR has a language-model bias toward *common words*. After
"Hola, ___, soy Leti," the likeliest token is "prima" (cousin), so when the
acoustics are murky the four witnesses all slid the real name "Selma" toward
prima / primas / Prisma. Consensus correctly FLAGS the token (low confidence +
disagreement) but cannot INVENT the name. This module closes that loop: given a
garbled name-slot token (or a human's phonetic impression like "sema"), it
surfaces the closest REAL Spanish given names so a person can pick.

HONEST LIMITS (same spine as the rest of the engine):
  1. It SURFACES candidates; it does NOT decide. severity 'review' (weight 0).
  2. The gazetteer is curated common given names, not a census authority yet —
     so absence from it is not proof a token isn't a name.
  3. Phonetic matching is strongest when fed a clean phonetic impression
     ("sema" -> Selma/Zelma); on raw ASR garble ("Prisma") it is weaker. The
     human ear + this shortlist together resolve the name; neither alone does.
"""
from __future__ import annotations
import os, json, re, unicodedata, functools
from .types import Flag, Transcript
from .lexicon import is_known

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "es_names.json")
_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


def _fold(s: str) -> str:
    """lowercase + strip diacritics."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def phonetic_key(s: str) -> str:
    """Collapse a Spanish word to its sound, so spellings that sound alike share a
    key: b==v, z/ce/ci==s (seseo), j/ge/gi==x, ll==y, h silent, qu==k, rr==r,
    ñ==ny, and runs of a repeated sound collapse. Selma/Zelma -> 'selma'."""
    s = _fold(s)
    s = s.replace("qu", "k").replace("ll", "y").replace("rr", "r").replace("ñ", "ny")
    res, n = [], len(s)
    for i, c in enumerate(s):
        nxt = s[i + 1] if i + 1 < n else ""
        if c == "h":
            continue                       # silent
        elif c in "vw":
            res.append("b")                # b == v
        elif c == "z":
            res.append("s")                # seseo
        elif c == "c":
            res.append("s" if nxt in "ei" else "k")
        elif c == "j":
            res.append("x")
        elif c == "g":
            res.append("x" if nxt in "ei" else "g")
        else:
            res.append(c)
    out = []
    for ch in res:                         # collapse consecutive duplicates
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def _lev(a: str, b: str) -> int:
    """Levenshtein edit distance (small strings, no deps)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@functools.lru_cache(maxsize=1)
def _names() -> list:
    try:
        return json.load(open(_DATA, encoding="utf-8")).get("names", [])
    except Exception:
        return []


@functools.lru_cache(maxsize=1)
def _name_folded() -> set:
    return {_fold(n) for n in _names()}


@functools.lru_cache(maxsize=1)
def _name_keys() -> list:
    """[(phonetic_key, display_name)] for ranking."""
    return [(phonetic_key(n), n) for n in _names()]


def is_name(token: str) -> bool:
    """token is a known Spanish given name (accent/case-insensitive)."""
    return _fold(token) in _name_folded()


def candidates(heard: str, n: int = 6, max_dist: int = 3) -> list:
    """Real given names closest to a heard/garbled token, ranked by phonetic edit
    distance (tie-break: raw fold distance, then length). Feed it the ASR token OR
    a human phonetic impression ('sema'). Returns [(name, score)] best first."""
    hk, hf = phonetic_key(heard), _fold(heard)
    scored = []
    for nk, name in _name_keys():
        d = _lev(hk, nk)
        if d <= max_dist:
            scored.append((d, _lev(hf, _fold(name)), abs(len(nk) - len(hk)), name))
    scored.sort()
    seen, out = set(), []
    for d, d2, _, name in scored:
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append((name, d))
        if len(out) >= n:
            break
    return out


def make_name_surfacer(lang: str = "es", min_zipf: float = 3.0):
    """Scanner: a token that is NOT a known Spanish word, NOT frequent, but IS a
    STRONG phonetic match (edit distance <=1) to a real given name gets surfaced
    (review-tier) with candidate names. Catches the out-of-vocabulary name garble
    the lexicon check alone passes over (e.g. 'Selba' -> Selma).

    Two gates keep it quiet: the frequency escape (a common word like 'soy'/'oye'
    that pyspellchecker happens to lack is NOT a name) and the distance<=1 match
    (a weak distance-2 coincidence like 'hablame'->Abraham does not fire)."""
    from wordfreq import zipf_frequency

    def name_surfacer(t: Transcript) -> list:
        out = []
        for ln in t.lines:
            seen = set()
            for m in _WORD.finditer(ln.text):
                w = m.group(0)
                wl = _fold(w)
                if wl in seen or len(wl) < 3:
                    continue
                if is_known(w, lang) or is_name(w):
                    continue                          # real word or known name
                if zipf_frequency(wl, lang) >= min_zipf:
                    continue                          # common word, not a name garble
                cands = candidates(w, n=5)
                if cands and cands[0][1] <= 1:        # STRONG match to a real name
                    seen.add(wl)
                    names = ", ".join(nm for nm, _ in cands)
                    out.append(Flag(
                        rule="es_name_candidate", severity="review", line=ln.n, evidence=w,
                        label=f"Possible name '{w}' — not a known word; sounds like a given name",
                        fix=f"Confirm by ear; candidates: {names}"))
        return out
    return name_surfacer
