"""Spanish homophone-trap surfacer — the Latin-script analog of semantic.py.

Loads data/es_confirmed.json (haya/halla/aya, vaya/valla/baya, hecho/echo, tú/tu,
sí/si, a ver/haber …) and SURFACES any confirmed-homophone member word in the text
for human review.

HONEST LIMITS (by design, same spine as the rest of the engine):
  1. It SURFACES the trap; it does NOT decide which spelling is right — that needs
     grammar/context a deterministic table can't supply. So: severity 'review'
     (weight 0, never moves the grade), no Thoth fixers.
  2. The KB is LLM-built, NOT RAE/authority-grounded (STATUS). Review-tier only,
     never a hard error, until a wordfreq/RAE sweep grounds it.

Matching is accent-insensitive (sí==si for lookup) and whole-word (so 'si' does
not fire inside 'siempre'); multiword members ('a ver') are matched with boundaries.
"""
from __future__ import annotations
import os, json, re, unicodedata, functools
from .types import Flag, Transcript

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "es_confirmed.json")
_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


def _fold(s: str) -> str:
    """lowercase + strip diacritics, so the index is accent-insensitive."""
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


@functools.lru_cache(maxsize=1)
def _entries():
    try:
        data = json.load(open(_DATA, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for e in data:
        members = [(o.get("word", "").strip(), o.get("gloss", "")) for o in e.get("options", [])]
        members = [(w, g) for w, g in members if w]
        if len(members) >= 2:
            out.append({"key": e.get("key", ""), "reading": e.get("reading", ""), "members": members})
    return out


@functools.lru_cache(maxsize=1)
def _single_index():
    idx = {}
    for e in _entries():
        for w, _ in e["members"]:
            if " " not in w:
                idx.setdefault(_fold(w), e)
    return idx


@functools.lru_cache(maxsize=1)
def _multiword():
    return [(_fold(w), e) for e in _entries() for w, _ in e["members"] if " " in w]


ENTRY_COUNT = len(_entries())


def _alts(e) -> str:
    return " / ".join(f"{w} = {g}" for w, g in e["members"])


def homophone_traps(t: Transcript) -> list[Flag]:
    sidx, multi = _single_index(), _multiword()
    out = []
    for ln in t.lines:
        folded = _fold(ln.text)
        hits = {}   # entry key -> (surface shown, entry)  (one flag per trap per line)
        for m in _WORD.finditer(ln.text):
            e = sidx.get(_fold(m.group(0)))
            if e and e["key"] not in hits:
                hits[e["key"]] = (m.group(0), e)
        for fp, e in multi:
            if e["key"] not in hits and re.search(r"\b" + re.escape(fp) + r"\b", folded):
                hits[e["key"]] = (fp, e)
        for surf, e in hits.values():
            out.append(Flag(
                rule="es_homophone_trap", severity="review", line=ln.n, evidence=surf,
                label=f"Spanish homophone trap: '{surf}' ({e['reading']}) — confirm by meaning",
                fix=f"Same sound, pick by context: {_alts(e)}"))
    return out
