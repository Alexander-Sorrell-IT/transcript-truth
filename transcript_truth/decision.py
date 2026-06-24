"""Generic collocation-grounded DECISION layer (the JP context_homophones analog,
made language-agnostic). For a confusable word in context, score each member of its
trap-set by collocation overlap with the sentence's other words, and if a DIFFERENT
member fits the context better (by a margin) flag it as the likely-correct one.

Turns "surface the trap" (review) into "auto-resolve" (a real correction). Data:
data/<lang>_collocations.json (Leipzig) + data/<lang>_confirmed.json (trap sets).
"""
from __future__ import annotations
import json, os, re, functools
from .types import Flag, Transcript

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@functools.lru_cache(maxsize=8)
def _colloc(lang: str):
    try:
        return json.load(open(os.path.join(_DATA, f"{lang}_collocations.json"), encoding="utf-8"))
    except Exception:
        return {}


@functools.lru_cache(maxsize=8)
def _sets(lang: str):
    """member-word(lower) -> the full list of single-word members of its trap-set."""
    try:
        data = json.load(open(os.path.join(_DATA, f"{lang}_confirmed.json"), encoding="utf-8"))
    except Exception:
        return {}
    idx = {}
    for e in data:
        members = [(o.get("word") or "").strip().lower() for o in e.get("options", [])]
        members = [m for m in members if m and " " not in m and "-" not in m]
        if len(set(members)) >= 2:
            for m in members:
                idx.setdefault(m, members)
    return idx


def make_decision(lang: str, script: str = "latin", margin: int = 1):
    rx = re.compile(r"[Ѐ-ӿ]+" if script == "cyrillic" else r"[^\W\d_]+", re.UNICODE)

    def decision(t: Transcript) -> list[Flag]:
        col, sets = _colloc(lang), _sets(lang)
        out = []
        for ln in t.lines:
            words = [w.lower() for w in rx.findall(ln.text)]
            ctxall = set(words)
            for w in words:
                members = sets.get(w)
                if not members:
                    continue
                ctx = ctxall - {w}

                def score(m):
                    comp = set(col.get(m, []))
                    return len(comp & ctx) + sum(1 for c in ctx if m in col.get(c, []))

                scored = sorted(((score(m), m) for m in set(members)), reverse=True)
                best_s, best_m = scored[0]
                if best_m != w and best_s - score(w) >= margin and best_s > 0:
                    out.append(Flag(
                        rule=f"{lang}_decision", severity="moderate", line=ln.n, evidence=w,
                        label=f"{lang.upper()} likely-wrong confusable: '{w}' — context fits '{best_m}'",
                        fix=f"Replace '{w}' with '{best_m}' (collocation-grounded decision)."))
        return out
    decision.__name__ = f"{lang}_decision"
    return decision
