"""Pitch-accent witness (Tokyo accent). Same-reading homophones often differ in
PITCH (箸 hashi atamadaka vs 橋 hashi odaka vs 端 hashi heiban) — a signal that is
in the audio but invisible to a text-only or kana-level check. This module turns
the verdict layer's "AMBIGUOUS, give up" into two honest buckets:

  - DIFFERENT accent  -> resolvable by ear: tell the listener exactly what to
    listen for (the downstep position).
  - SAME accent       -> genuinely identical in sound (華氏/菓子, 動悸/動機):
    truly context-only, the irreducible core. Stays AMBIGUOUS.

Data: data/jp_pitch_accent.json (kanjium), word -> [{reading, accent}], accent =
mora drop position (0 = heiban/flat, 1 = atamadaka, n = drop after mora n; comma
= multiple accepted patterns). No model — pure dictionary lookup.
"""
from __future__ import annotations
import os, json, functools

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SMALL = set("ゃゅょゎァィゥェォャュョヮ")   # combine with the preceding kana into one mora


@functools.lru_cache(maxsize=1)
def _entries():
    try:
        return json.load(open(os.path.join(_DIR, "data", "jp_pitch_accent.json"), encoding="utf-8"))["entries"]
    except FileNotFoundError:
        return {}


def _to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _morae(reading: str):
    out = []
    for ch in _to_hira(reading):
        if ch in _SMALL and out:
            out[-1] += ch
        else:
            out.append(ch)
    return out


def accents(surface: str, reading: str | None = None) -> set:
    """Set of accent positions (ints) for a surface, optionally filtered to a reading."""
    out = set()
    for e in _entries().get(surface, []):
        if reading is not None and _to_hira(e["reading"]) != _to_hira(reading):
            continue
        for a in str(e.get("accent", "")).split(","):
            a = a.strip()
            if a.lstrip("-").isdigit():
                out.add(int(a))
    return out


def acc_type(reading: str, accent: int) -> str:
    n = len(_morae(reading))
    if accent == 0:
        return "heiban (flat — no drop, stays high onto the next word)"
    if accent == 1:
        return "atamadaka (drops right after the first mora)"
    if accent == n:
        return "odaka (drops on the following particle)"
    return f"nakadaka (drops after mora {accent})"


def distinguish(surf_a: str, surf_b: str, reading: str) -> dict:
    """Do two same-reading homophones differ in pitch accent? distinguishable=True
    means their accent sets are disjoint → the audio's pitch can tell them apart."""
    aa, bb = accents(surf_a, reading), accents(surf_b, reading)
    have = bool(aa) and bool(bb)
    return {"a": sorted(aa), "b": sorted(bb), "have_data": have,
            "distinguishable": have and aa.isdisjoint(bb)}


def hint(surf_a: str, surf_b: str, reading: str) -> str | None:
    """Human-readable 'listen for this' string when the pair is pitch-distinguishable."""
    d = distinguish(surf_a, surf_b, reading)
    if not d["distinguishable"]:
        return None
    a = f"{surf_a}=accent {','.join(map(str, d['a']))} [{acc_type(reading, d['a'][0])}]"
    b = f"{surf_b}=accent {','.join(map(str, d['b']))} [{acc_type(reading, d['b'][0])}]"
    return f"{a}; {b}"
