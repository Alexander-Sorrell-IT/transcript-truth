"""Spoken-Japanese layer for transcription.

Two parts, because spoken != written:
  1. SLANG/COLLOQUIAL dictionary — loaded from data/jp_colloquial.json (the
     JMdict slang/col/net-sl/on-mim/abbr subset, 11k+ entries). Lookup, not
     auto-scan (too many 2-char common forms to scan blindly).
  2. CONTRACTION map — the spoken reductions JMdict has NO headword for
     (してる←している, なきゃ←なければ). This is the 'shorter form' layer:
     recognize the casual form so QA doesn't false-flag it AND knows its standard
     equivalent for disambiguation.
"""
from __future__ import annotations
import json
import os
from .types import Flag, Transcript

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jp_colloquial.json")


def _load_slang():
    try:
        return json.load(open(_DATA, encoding="utf-8"))
    except Exception:
        return []


SLANG = _load_slang()
SLANG_COUNT = len(SLANG)
_SLANG_BY_FORM = {e["form"]: e for e in SLANG if e.get("form")}


def slang_lookup(word: str):
    """Is this token a known slang/colloquial form? Returns the entry or None."""
    return _SLANG_BY_FORM.get(word)


# High-confidence casual contractions: casual -> (standard, gloss). Longest-match-first.
CONTRACTIONS = {
    "とかなきゃ": ("ておかなければ", "must do in advance"),
    "なくちゃ": ("なくては", "must / have to"),
    "なきゃ": ("なければ", "must / if not"),
    "わかんない": ("わからない", "don't know / understand"),
    "ちゃう": ("てしまう", "end up …-ing / completely"),
    "じゃう": ("でしまう", "end up …-ing (voiced)"),
    "じゃん": ("じゃないか", "…right? / tag question"),
    "すげー": ("すごい", "amazing (emphatic)"),
    "すげえ": ("すごい", "amazing (emphatic)"),
    "やべー": ("やばい", "crazy / awesome (emphatic)"),
    "まじで": ("本当に", "seriously / really"),
    "やっぱ": ("やはり", "as expected / after all"),
    "っす": ("です", "casual-polite copula"),
    "とく": ("ておく", "do in advance"),
    "てる": ("ている", "progressive / ongoing state"),
}
_ORDER = sorted(CONTRACTIONS, key=len, reverse=True)


def casual_forms(t: Transcript) -> list[Flag]:
    """Flag spoken contractions with their standard equivalents (severity: review)."""
    out: list[Flag] = []
    for ln in t.lines:
        claimed: list[str] = []
        for c in _ORDER:
            if c in ln.text and not any(c in longer for longer in claimed):
                std, gloss = CONTRACTIONS[c]
                claimed.append(c)
                out.append(Flag(
                    rule="casual_form", label=f"Casual '{c}' = standard '{std}'",
                    line=ln.n, severity="review", evidence=c, fix=gloss,
                ))
    return out


# ---------------------------------------------------------------------------
# Generic multilingual layer — data/<lang>_colloquial.json (kaikki/Wiktionary,
# built by bench/build_colloquial_multilang.py; same shape as the JP cell).
# Lookup-not-scan, exactly like the JP layer above.
# ---------------------------------------------------------------------------
import functools as _functools

_DATA_DIR = os.path.dirname(_DATA)


@_functools.lru_cache(maxsize=16)
def _lang_cell(lang: str):
    """{form_lower: entry} for one language's colloquial/idiom cell ({} if absent)."""
    try:
        entries = json.load(open(os.path.join(_DATA_DIR, f"{lang}_colloquial.json"),
                                 encoding="utf-8"))
        return {e["form"].lower(): e for e in entries if e.get("form")}
    except Exception:
        return {}


def slang_lookup_lang(word: str, lang: str):
    """Known colloquial/slang/idiom form in `lang`? Entry or None. ja uses the JP cell."""
    if lang in ("ja", "jp"):
        return slang_lookup(word)
    return _lang_cell(lang).get(word.lower())


def known_colloquial(word: str, lang: str) -> bool:
    """Validity signal for the adjudicator: slang words ('chelou') are NOT in spellcheckers,
    and without this they look like garble and can lose to a dictionary near-variant."""
    return slang_lookup_lang(word, lang) is not None
