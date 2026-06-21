"""Coherence witness, constrained + deterministically gated.

Open-ended "Qwen, what's the right word?" fails — it invents non-homophones (菓子->気温).
So instead: the DETERMINISTIC layer enumerates the same-reading candidates from the full
JMdict reading index, and Qwen only PICKS the contextually-best one from that closed list.
It cannot invent. A flag fires only when Qwen's pick differs from the written word AND is a
real same-reading candidate — catching thin-context homophones (菓子90度 -> 華氏90度).
"""
import os, json, functools
from sudachipy import dictionary, tokenizer
from .types import Flag
from .verdict import gloss
from .worker import qwen

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tok = dictionary.Dictionary().create()
_C = tokenizer.Tokenizer.SplitMode.C
_CONTENT = {"名詞", "動詞", "形容詞"}


def _kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


@functools.lru_cache(maxsize=1)
def reading_index():
    try:
        return json.load(open(os.path.join(_DIR, "data", "jp_reading_index.json"), encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _en(w):
    g = gloss(w)
    return f"{w} ({', '.join(g[:2])})" if g else w


def coherence_homophones(text, max_checks=5):
    """For each content word with same-reading alternatives, BLANK it and ask Qwen to
    fill the blank from the closed candidate list. Blanking removes the anchor, so Qwen
    reasons from context instead of rubber-stamping what's written. If its fill differs
    from the written word (and is a real same-reading candidate), flag it. One Qwen call
    per checked word; capped at max_checks."""
    ridx = reading_index()
    flags, seen = [], set()
    for m in _tok.tokenize(text, _C):
        s = m.surface()
        if m.part_of_speech()[0] not in _CONTENT or len(s) < 2 or s in seen:
            continue
        cands = ridx.get(_kata2hira(m.reading_form()))
        if not cands or s not in cands or len(cands) < 2:
            continue
        seen.add(s)
        if len(seen) > max_checks:
            break
        blanked = text.replace(s, "___", 1)
        opts = "、".join(cands[:12])
        try:
            fill = qwen([{"role": "user", "content":
                "文の___に入る最も適切な語を候補から1つだけ選び、漢字のみ答えてください。\n"
                f"文：{blanked}\n候補：{opts}"}], max_tokens=15).strip(" 「」。、（）()")
        except Exception:
            continue
        if fill and fill != s and fill in cands:
            flags.append(Flag(
                rule="coherence_homophone", severity="review",
                label=f"{_en(s)} may be wrong — {_en(fill)} fits the context (same sound)",
                evidence=s, fix=f"Consider {fill} — same reading, fits the meaning."))
    return flags
