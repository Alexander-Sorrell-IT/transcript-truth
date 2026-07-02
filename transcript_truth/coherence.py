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


def _qwen_voter(prompt):
    return qwen([{"role": "user", "content": prompt}], max_tokens=15)


def coherence_homophones(text, max_checks=5, voters=None):
    """For each content word with same-reading alternatives, BLANK it and ask the voter LLM(s) to
    fill the blank from the closed candidate list. Blanking removes the anchor, so the model reasons
    from context instead of rubber-stamping what's written; the closed list means it can't invent a
    non-homophone. A flag fires only when a MAJORITY of voters agree on the SAME candidate that
    differs from the written word (MODEL_MAP.md Stage 4): with one voter that's its pick (original
    behavior); with two gated voters (Qwen + Gemini) both must agree — cutting false positives.
    Unanimous multi-voter picks are marked higher-confidence. Capped at max_checks words."""
    from collections import Counter
    voters = voters or [_qwen_voter]
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
        prompt = ("文の___に入る最も適切な語を候補から1つだけ選び、漢字のみ答えてください。\n"
                  f"文：{blanked}\n候補：{opts}")
        picks = []
        for v in voters:
            try:
                fill = (v(prompt) or "").strip(" 「」。、（）()")
            except Exception:
                continue
            if fill and fill != s and fill in cands:      # gated: real same-reading candidate only
                picks.append(fill)
        if not picks:
            continue
        top, n = Counter(picks).most_common(1)[0]
        if n <= len(voters) / 2:                          # need a majority of voters to agree
            continue
        conf = " (both models agree)" if len(voters) > 1 and n == len(voters) else ""
        flags.append(Flag(
            rule="coherence_homophone", severity="review",
            label=f"{_en(s)} may be wrong — {_en(top)} fits the context (same sound){conf}",
            evidence=s, fix=f"Consider {top} — same reading, fits the meaning."))
    return flags
