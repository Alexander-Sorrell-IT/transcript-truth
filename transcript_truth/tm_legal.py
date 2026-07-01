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
# references or words like page, paragraph, or line ... do not get capitalized"). Only fires in a
# REFERENCE context — the term must be followed by a NUMBER — so a surname/proper noun ("Officer
# Page", "Number Two", "Line dance") is never flagged. Lookbehind spares sentence-initial capitals.
_LC_TERMS = re.compile(r"(?<=[a-z,;:\-] )(Number|Page|Paragraph|Line)\b(?=\s+\d)")


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


# --- Legal Entrance Exam: structural rules (Colloquy / Q&A / dashes) ---
# Colloquy speaker IDs are ALL CAPS — surnames for lawyers (MR. SMITH), titles for judges
# (THE COURT), THE WITNESS; Q/A for examination (guide p.3). A speaker label = a name-like prefix
# at line start followed by 2+ spaces (the WorkHub tab separator; CVL body text is single-spaced).
_SPK = re.compile(r"^\s*([A-Za-z][A-Za-z .'\-]{0,37}?[A-Za-z])\s{2,}\S")
# ...but a stray mid-sentence double space is NOT a label. Only flag a prefix that is actually a
# recognized legal title/role (in the wrong case) — never arbitrary prose ("Well  I don't know",
# "I went to the store  and..."). Bare-surname labels without a title aren't flagged (can't be told
# from prose), which keeps zero false positives on ordinary sentences.
_LABEL_MARKERS = (
    "mr", "ms", "mrs", "dr", "miss", "mister", "madam", "sir",
    "judge", "justice", "officer", "detective", "sergeant", "lieutenant", "captain",
    "deputy", "attorney", "counsel", "counselor", "chief", "doctor", "professor",
    "the court", "the witness", "the clerk", "the bailiff", "the reporter",
    "the interpreter", "the defendant", "the plaintiff", "the foreperson", "the jury",
    "by mr", "by ms", "by mrs", "by the",
)


def _is_legal_label(lab: str) -> bool:
    low = lab.lower()
    return any(low == k or low.startswith(k + " ") or low.startswith(k + ".") for k in _LABEL_MARKERS)


def tm_speaker_caps(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        m = _SPK.match(ln.text)
        if not m:
            continue
        lab = m.group(1).strip()
        if lab in ("Q", "A") or not _is_legal_label(lab):   # only recognized legal labels
            continue
        if any(c.islower() for c in lab):                   # a legal label with lowercase → not all caps
            out.append(Flag(
                rule="tm_speaker_caps", severity="moderate", line=ln.n, evidence=lab,
                label=f"Legal: speaker ID '{lab}' must be ALL CAPS (Colloquy)",
                fix=f"Write '{lab.upper()}' — Colloquy speaker IDs are all caps."))
    return out


# Double dashes (false starts, interruptions, repetitions) ATTACH to the preceding word —
# 'word-- next', never 'word -- next' (a space-both-sides single dash is the offset rule). [p.10]
_SPACE_BEFORE_DDASH = re.compile(r"(?<=\w) -- ")


def tm_double_dash(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _SPACE_BEFORE_DDASH.finditer(ln.text):
            out.append(Flag(
                rule="tm_double_dash", severity="minor", line=ln.n, evidence=m.group(0).strip() or "--",
                label="Legal: double dash attaches to the preceding word — no space before '--'",
                fix="Write 'word-- next'; the dashes attach to the word before them (single dash ' - ' is the offset rule)."))
    return out


# Spoken punctuation (p.24): when a speaker DICTATES punctuation ("comma", "period", "stop"…), omit
# the word and use the actual mark. The tell that it's dictated (not the noun "comma"/"period") is
# that it sits adjacent to real punctuation: ", comma," or "…, stop." — high-precision.
_SPOKEN_PUNCT = re.compile(
    r",\s*(comma|semicolon|colon)\s*,|,\s*(period|full stop|stop)\s*(?=\.|$|\s[A-Z])", re.I)


def tm_spoken_punct(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        ms = list(_SPOKEN_PUNCT.finditer(ln.text))
        for m in ms:
            is_terminal = bool(m.group(2))          # period/stop/full stop (comma-guarded → unambiguous)
            # a lone ", comma," / ", colon," is ambiguous with a sentence that merely NAMES the marks
            # ("use a colon, comma, or period") — require 2+ dictation hits before firing on those.
            if not is_terminal and len(ms) < 2:
                continue
            word = (m.group(1) or m.group(2))
            out.append(Flag(
                rule="tm_spoken_punct", severity="moderate", line=ln.n, evidence=word,
                label=f"Legal: dictated punctuation '{word}' should be omitted, using only the mark",
                fix=f"Remove the spoken word '{word}' and keep only the actual punctuation. [p.24]"))
    return out
