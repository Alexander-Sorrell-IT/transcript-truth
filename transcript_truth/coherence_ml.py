"""Generic coherence witness (the JP coherence_homophones analog, language-agnostic).

For each confusable word in the text, BLANK it and ask an LLM to pick the best fit
from that trap-set's CLOSED member list. Blanking removes the anchor so the model
reasons from context; the closed list means it can't invent. A flag fires only when
the pick differs from the written word AND is a real set member.

This is the right tool for GRAMMATICAL homophones (there/their, haya/halla) that the
collocation decision layer can't separate. LLM-based -> severity 'review' (opt-in),
the engine's deliberate exception to "no model in the verdict".
"""
from __future__ import annotations
import os, json, re, urllib.request
from .types import Flag, Transcript
from .witness import _key

_WORD = {"cyrillic": re.compile(r"[Ѐ-ӿ]+"), "latin": re.compile(r"[^\W\d_]+", re.UNICODE)}


def _gemini_text(prompt: str) -> str:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    key = _key("GEMINI_API_KEY")
    for mdl in ("gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent"
        req = urllib.request.Request(url, data=body,
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            continue
    return ""


def make_coherence(lang: str, script: str = "latin", max_checks: int = 6):
    rx = _WORD["cyrillic"] if script == "cyrillic" else _WORD["latin"]

    def coherence(t: Transcript) -> list[Flag]:
        from .lexicon import _conf
        single, _ = _conf(lang)
        out = []
        for ln in t.lines:
            seen, checks = set(), 0
            for m in rx.finditer(ln.text):
                w = m.group(0); wl = w.lower()
                e = single.get(wl)
                if not e or wl in seen:
                    continue
                members = [o.get("word", "") for o in e.get("options", []) if o.get("word")]
                if len(set(members)) < 2:
                    continue
                seen.add(wl); checks += 1
                if checks > max_checks:
                    break
                blanked = ln.text.replace(w, "___", 1)
                opts = " / ".join(members)
                pick = _gemini_text(
                    "Fill the blank with exactly ONE option from the list. "
                    "Answer with only that one word, nothing else.\n"
                    f"Sentence: {blanked}\nOptions: {opts}"
                ).strip(" .\"'\n").split()[:1]
                pick = pick[0] if pick else ""
                if pick and pick.lower() != wl and pick.lower() in [x.lower() for x in members]:
                    out.append(Flag(
                        rule=f"{lang}_coherence", severity="review", line=ln.n, evidence=w,
                        label=f"'{w}' may be wrong — '{pick}' fits the context (same sound)",
                        fix=f"Consider '{pick}'."))
        return out
    coherence.__name__ = f"{lang}_coherence"
    return coherence
