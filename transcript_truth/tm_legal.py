"""TranscribeMe Legal (CVL) rules captured from the actual TranscribeMe legal training course
(newworkhub.transcribeme.com/training/1). These are the deterministic, distinctive rules the
training spells out — folded in so the engine's legal QA matches TranscribeMe's real guide.
High-precision (whitelists / guarded patterns), so no false positives. Lives in the legal DOMAIN."""
from __future__ import annotations
import re
from .types import Flag, Transcript

# TranscribeMe legal allows ONLY these three sound tags (training: "The only sound tags allowed are
# [coughs], [sneezes], and [phone rings].") — any other event/sound tag is disallowed.
_ALLOWED_SOUND = {"coughs", "sneezes", "phone rings"}
# other bracket tags that are legitimately NOT sound tags (don't flag these)
_OK_TAGS = {"inaudible", "unintelligible", "phonetic", "sic", "crosstalk"}
# event/sound words that DO appear bracketed but are disallowed in TranscribeMe legal
_DISALLOWED_SOUND = {"laughs", "laughter", "applause", "sighs", "sigh", "cough", "sneeze",
                     "music", "pause", "silence", "background noise", "noise", "chuckles",
                     "clears throat", "clapping", "ringing"}
_BRACKET = re.compile(r"\[\s*([a-zA-Z][a-zA-Z ]+?)\s*\]")


def tm_sound_tags(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _BRACKET.finditer(ln.text):
            tag = m.group(1).strip().lower()
            if tag in _ALLOWED_SOUND or tag in _OK_TAGS:
                continue
            if tag in _DISALLOWED_SOUND:
                out.append(Flag(
                    rule="tm_sound_tag", severity="moderate", line=ln.n, evidence=m.group(0),
                    label=f"Legal: sound tag '{m.group(0)}' not allowed — only [coughs], [sneezes], [phone rings]",
                    fix="TranscribeMe legal permits only [coughs], [sneezes], [phone rings]; remove the rest."))
    return out


# Bates/reference terms stay lowercase even mid-reference (training: "the word 'number' in Bates
# references or words like page, paragraph, or line ... do not get capitalized"). Guard with a
# lookbehind so a legitimate sentence-initial capital isn't flagged.
_LC_TERMS = re.compile(r"(?<=[a-z,;:\-] )(Number|Page|Paragraph|Line)\b")


def tm_lowercase_terms(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _LC_TERMS.finditer(ln.text):
            w = m.group(1)
            out.append(Flag(
                rule="tm_lowercase", severity="minor", line=ln.n, evidence=w,
                label=f"Legal: '{w}' should be lowercase (page/paragraph/line/number stay lowercase)",
                fix=f"Write '{w.lower()}' — these reference terms are never capitalized in CVL."))
    return out
