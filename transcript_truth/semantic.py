"""Semantic trap detector — homophone (同音異義語) visibility, tokenizer-grounded.

Uses SudachiPy (a real Japanese morphological analyzer) to tokenize the text and
match homophone members by WORD + dictionary-form — precise (no substring false
positives) and conjugation-aware (犯した → dict form 犯す → matched), upgrading the
earlier regex which was substring-based and noun-only. Falls back to regex
substring matching if SudachiPy isn't installed.

Entries come from the persisted, adversarially-verified + JMdict-checked KB
(data/jp_confirmed.json). The detector emits 'review' flags — it surfaces the
decision; transcript_truth.disambiguate makes the call.
"""
from __future__ import annotations
import json
import os
import re
from .types import Flag, Transcript

_KANJI_LEAD = re.compile(r"^[一-鿿]")
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jp_confirmed.json")

_SEED = [{"key": "偏在/遍在", "reading": "へんざい", "options": [
    {"kanji": "偏在", "gloss": "unevenly distributed / concentrated"},
    {"kanji": "遍在", "gloss": "ubiquitous / everywhere"}]}]


def _is_member(s: str) -> bool:
    s = (s or "").strip()
    return bool(s) and len(s) <= 5 and bool(_KANJI_LEAD.match(s))   # kanji-led, short: nouns + verbs(+okurigana)


def _load_entries():
    try:
        data = json.load(open(_DATA, encoding="utf-8"))
    except Exception:
        data = _SEED
    entries = []
    for e in data:
        members = [((o.get("kanji") or "").strip(), o.get("gloss", "")) for o in (e.get("options") or [])]
        members = [(k, g) for k, g in members if _is_member(k)]
        if len(members) >= 2:
            entries.append({"key": e.get("key", ""), "reading": e.get("reading", ""),
                            "members": members, "note": e.get("note", "")})
    return entries


ENTRIES = _load_entries()
TRAP_COUNT = len(ENTRIES)
_MEMBER_INDEX = {}
for _e in ENTRIES:
    for _k, _ in _e["members"]:
        _MEMBER_INDEX.setdefault(_k, _e)

_TOKENIZER = None


def _get_tokenizer():
    """Lazily build a Sudachi tokenizer; cache False if unavailable."""
    global _TOKENIZER
    if _TOKENIZER is None:
        try:
            from sudachipy import dictionary, tokenizer
            # Mode A (short unit) so compounds like 人事異動 split into 人事+異動,
            # exposing the homophone member; members are single morphemes so they survive.
            _TOKENIZER = (dictionary.Dictionary().create(), tokenizer.Tokenizer.SplitMode.A)
        except Exception:
            _TOKENIZER = False
    return _TOKENIZER


def _alts(e) -> str:
    return " / ".join(f"{k}={g}" for k, g in e["members"])


def _flag(e, hit, line) -> Flag:
    return Flag(rule="homophone_trap",
                label=f"Homophone trap: '{hit}' ({e['reading']}) — confirm against meaning",
                line=line, severity="review", evidence=hit,
                fix=f"Same reading, pick by context: {_alts(e)}")


def homophone_traps(t: Transcript) -> list[Flag]:
    tok = _get_tokenizer()
    out: list[Flag] = []
    for ln in t.lines:
        if tok:
            m, mode = tok
            seen = set()
            for token in m.tokenize(ln.text, mode):
                for form in (token.surface(), token.dictionary_form()):
                    e = _MEMBER_INDEX.get(form)
                    if e and (e["key"], form) not in seen:
                        seen.add((e["key"], form))
                        out.append(_flag(e, form, ln.n))
                        break
        else:  # regex fallback (substring, noun-biased)
            for e in ENTRIES:
                hit = next((k for k, _ in e["members"] if k in ln.text), None)
                if hit:
                    out.append(_flag(e, hit, ln.n))
    return out
