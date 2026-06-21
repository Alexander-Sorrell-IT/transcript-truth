"""disambiguate — the DECISION layer for homophone traps.

The homophone detector SURFACES candidates (偏在/遍在 + glosses). This module
DECIDES between them by the 'translate-and-check' method: translate the sentence
under each candidate's meaning, keep the one that is COHERENT in context.

It is an LLM-judgment step — but structured + auditable, which is the whole point:
the chosen English rendering is returned, so a nonsensical pick is *visible* to a
reviewer (unlike the silent confident-wrong failure). The model call is injected
(llm_fn) so the package stays dependency-free; wire it to any model in production.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .semantic import ENTRIES


@dataclass
class Decision:
    sentence: str
    reading: str
    candidates: list = field(default_factory=list)   # [(kanji, gloss)]
    used: str = ""        # the kanji actually in the sentence
    pick: str = ""        # the contextually-correct kanji
    english: str = ""     # the coherent English rendering (audit trail)
    is_error: bool = False  # used != pick  -> the transcript has the wrong kanji
    confidence: str = "medium"


def find_trap(sentence: str):
    """Return (entry, member-in-sentence) for the first homophone trap present."""
    for e in ENTRIES:
        for k, _ in e["members"]:
            if k in sentence:
                return e, k
    return None, None


def build_prompt(sentence: str, reading: str, candidates) -> str:
    opts = "\n".join(f"  - {k} = {g}" for k, g in candidates)
    return (
        "You are disambiguating a Japanese homophone for a transcription QA tool.\n"
        f"The sentence contains a kanji read「{reading}」 — candidates sound identical but "
        "mean different things. For EACH candidate, translate the sentence into English "
        "using that meaning, then judge which translation is COHERENT in context. Pick the "
        "kanji whose translation makes sense; if genuinely ambiguous, say so and lower "
        "confidence.\n\n"
        f"SENTENCE: {sentence}\n\nCANDIDATES:\n{opts}\n\n"
        "Return: pick (the correct kanji), english (the coherent rendering), confidence."
    )


def disambiguate(sentence: str, llm_fn) -> "Decision | None":
    """llm_fn(prompt:str) -> {pick:str, english:str, confidence:str}. Returns None if
    no known homophone trap is present in the sentence."""
    entry, used = find_trap(sentence)
    if not entry:
        return None
    out = llm_fn(build_prompt(sentence, entry["reading"], entry["members"])) or {}
    pick = out.get("pick", used)
    return Decision(
        sentence=sentence, reading=entry["reading"], candidates=entry["members"],
        used=used, pick=pick, english=out.get("english", ""),
        is_error=(pick != used), confidence=out.get("confidence", "medium"),
    )
