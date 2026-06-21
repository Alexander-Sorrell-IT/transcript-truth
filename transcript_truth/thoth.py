"""Thoth — deterministic auto-fix for transcript-truth.

The scribe-god rewrites the transcript into its correct form. Profile-agnostic:
it applies whatever fixer set the chosen profile carries (default = Japanese +
GoTranscript English, legal = CVL "Redline", me = Alex's apostrophes on top).

NO model, same spine as the rest of the engine: every fix is one of the SAME
compiled patterns the scanners detect with, applied via re.sub — so detection
and correction can never drift, and word boundaries are respected. Only
deterministic, ~always-correct fixes are applied; 'review'-tier judgment calls
(homophones a sentence could go either way on, cant/wont, つなぎ言葉 that might be
real words) are never auto-applied — they stay flags for the human, the same
boundary the whole engine keeps.

    from transcript_truth.thoth import thoth
    fixed, changes = thoth(open("file.txt").read(), profile="legal")
"""
from __future__ import annotations
import re
from typing import List, Tuple
from .profiles import get as get_profile

# Label-aware split so the Q&A / speaker-label gap is NEVER collapsed by cleanup.
_LABELS = [
    re.compile(r"^\s*(?:[A-Z][A-Z .'-]{0,38}|Q|A)\s{2,}"),   # legal colloquy: "MR. JONES    "
    re.compile(r"^\s*[^:：]{1,40}?[：:]\s"),                   # "Speaker 1: " (ASCII/full-width colon)
]


def _split_label(text: str) -> Tuple[str, str]:
    for rx in _LABELS:
        m = rx.match(text)
        if m:
            return text[:m.end()], text[m.end():]
    return "", text


def thoth(text: str, profile: str = "default") -> Tuple[str, List[Tuple[int, str, str]]]:
    """Return (fixed_text, changes), changes = [(line_no, before, after), ...].

    Only lines that actually changed appear in `changes`."""
    prof = get_profile(profile)
    out: List[str] = []
    changes: List[Tuple[int, str, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        label, body = _split_label(line)
        new = body
        for pat, repl in prof.fixers:
            new = pat.sub(repl, new)
        # Cleanup on the BODY only (label gap preserved): collapse runs, kill
        # space-before-punctuation (ASCII + full-width). Fixers are written not to
        # create double spaces, so this mostly catches pre-existing spacing slips.
        new = re.sub(r"[ \t]{2,}", " ", new)
        new = re.sub(r"　{2,}", "　", new)
        new = re.sub(r"[ \t　]+([,.;:?!、。？！」』）])", r"\1", new)
        new = new.rstrip()
        if new != body.rstrip():
            changes.append((i, body.strip(), new.strip()))
        out.append(label + new)
    return "\n".join(out), changes
