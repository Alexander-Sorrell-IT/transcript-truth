"""Daily Transcription (DT) style guide — English, verbatim-leaning clean.

Built from the FULL coverage audit of DT_Style_Guide.txt + DT_Sample_Template.txt
(2026-07-07): the default English profile is GoTranscript rules and at least four of
them contradict DT (yeah->yes, 'you know' filler-flag, double-space flag, [inaudible]
vocabulary). This profile enforces what DT actually grades:

  header block -> timecoded FILENAME lines -> ALL-CAPS speaker labels -> DT tag
  vocabulary -> double-dash form -> [end of file: NAME] marker.

Source guide is CONFIDENTIAL (local use only) — rules here are re-expressed, not copied.
"""
from __future__ import annotations
import re
from .types import Flag, Transcript
from .legal_rules import legal_dash_form, legal_repeated_words, legal_partial_words


def _flag(rule, label, line, ev, fix, sev="moderate"):
    return Flag(rule=rule, label=label, line=line, severity=sev, evidence=ev, fix=fix)


# ---------------------------------------------------------------- header block (guide + template)
_HDR_TRANSCRIBED = re.compile(r"^TRANSCRIBED BY DAILY TRANSCRIPTION_[A-Z]{2,3}\s*$")
_HDR_FILENAME = re.compile(r"^FILE NAME:\s*\S+", re.I)


def dt_header(t: Transcript) -> list[Flag]:
    """First lines must be the 5-line header ending in TRANSCRIBED BY DAILY TRANSCRIPTION_XX."""
    head = [ln for ln in t.lines[:8]]
    text5 = [ln.text for ln in head]
    out = []
    if not any(_HDR_TRANSCRIBED.match(x or "") for x in text5):
        out.append(_flag("dt_header", "Missing 'TRANSCRIBED BY DAILY TRANSCRIPTION_<initials>' header line",
                         head[0].n if head else 1, (text5[0] if text5 else "")[:40],
                         "Header block: project / description / FILE NAME / date / TRANSCRIBED BY DAILY TRANSCRIPTION_XX."))
    if not any(_HDR_FILENAME.match(x or "") for x in text5):
        out.append(_flag("dt_header", "Missing 'FILE NAME:' header line",
                         head[0].n if head else 1, (text5[0] if text5 else "")[:40],
                         "Include 'FILE NAME: <exact audio file name>' in the header block."))
    return out


# ---------------------------------------------------------------- end-of-file marker
_EOF = re.compile(r"\[end of file:?\s*.+\]", re.I)


def dt_end_of_file(t: Transcript) -> list[Flag]:
    tail = " ".join(ln.text for ln in t.lines[-3:])
    if not _EOF.search(tail):
        last = t.lines[-1] if t.lines else None
        return [_flag("dt_eof", "Missing '[end of file: FILE NAME]' marker",
                      last.n if last else 1, (last.text if last else "")[:40],
                      "End with the last timecode line, then '[end of file: <FILE NAME>]'.")]
    return []


# ---------------------------------------------------------------- timecode lines
# FILENAME + five spaces + [HH:MM:SS]; no frames; roughly periodic.
_TC = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")
_TC_FRAMES = re.compile(r"\[\d{2}:\d{2}:\d{2}:\d{2}\]")
_TC_LINE = re.compile(r"^\S.*\s{5}\[\d{2}:\d{2}:\d{2}\]\s*$")


def dt_timecodes(t: Transcript) -> list[Flag]:
    out = []
    marks = []
    for ln in t.lines:
        if _TC_FRAMES.search(ln.text):
            out.append(_flag("dt_timecode", "Frames in timecode — DT uses [HH:MM:SS] only",
                             ln.n, ln.text.strip()[:40], "Drop the frame field: [00:05:30]."))
        m = _TC.search(ln.text)
        if m:
            marks.append((ln.n, int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))))
            if "[end of file" not in ln.text.lower() and not _TC_LINE.match(ln.text):
                out.append(_flag("dt_timecode", "Timecode line must be 'FILE NAME' + five spaces + [HH:MM:SS]",
                                 ln.n, ln.text.strip()[:50],
                                 "Format: MYFILE     [00:05:30] (exactly five spaces).", "review"))
    for (n0, s0), (n1, s1) in zip(marks, marks[1:]):
        if s1 - s0 > 90:
            out.append(_flag("dt_timecode_gap", f"{s1-s0}s between timecodes — DT wants ~every 30s / each answer",
                             n1, f"[gap {s0}s -> {s1}s]", "Insert intermediate timecode lines.", "review"))
    return out


# ---------------------------------------------------------------- speaker labels
# ALL-CAPS first name (or Q, MALE 1, FEMALE 1) + colon + TWO spaces.
_LABEL = re.compile(r"^([A-Za-z][A-Za-z .]{0,24}?\d{0,2}):(\s*)(\S)")


def dt_speaker_labels(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        m = _LABEL.match(ln.text)
        if not m:
            continue
        name, gap = m.group(1), m.group(2)
        if name.upper() in ("FILE NAME", "DATE", "PROJECT"):        # header lines, not speakers
            continue
        if name != name.upper():
            out.append(_flag("dt_speaker", f"Speaker label '{name}:' must be ALL CAPS",
                             ln.n, name + ":", f"Write '{name.upper()}:'."))
        if len(gap) != 2:
            out.append(_flag("dt_speaker", f"Speaker label needs exactly TWO spaces after the colon (found {len(gap)})",
                             ln.n, (name + ":" + gap)[:20] + "…", "NAME: <two spaces> dialogue.", "review"))
    return out


# ---------------------------------------------------------------- DT tag vocabulary
_ALLOWED_TAGS = {"background noise", "indiscernible", "overlap", "laugh", "cough", "crying",
                 "makes noise", "clears throat", "phonetic", "end of interview", "new interview",
                 "non-interview", "silence", "foreign language"}
_BANNED_MAP = {"giggles": "laugh", "giggle": "laugh", "chuckles": "laugh", "chuckle": "laugh",
               "laughs": "laugh", "laughing": "laugh", "laughter": "laugh",
               "coughs": "cough", "coughing": "cough", "cries": "crying",
               "inaudible": "indiscernible", "unintelligible": "indiscernible",
               "crosstalk": "overlap", "cross-talk": "overlap", "cross talk": "overlap"}
_TAG = re.compile(r"\[([a-z][a-z -]{1,25})\]", re.I)


def dt_tags(t: Transcript) -> list[Flag]:
    out = []
    for ln in t.lines:
        for m in _TAG.finditer(ln.text):
            tag = m.group(1).strip().lower()
            if tag in _ALLOWED_TAGS or _TC.search(m.group(0)):
                continue
            if re.fullmatch(r"[a-z' -]+\?", tag):                   # [word?] questionable form — allowed
                continue
            if tag in _BANNED_MAP:
                out.append(_flag("dt_tag", f"'[{tag}]' is not a DT tag",
                                 ln.n, m.group(0), f"Use '[{_BANNED_MAP[tag]}]'."))
            else:
                out.append(_flag("dt_tag", f"'[{tag}]' is not in DT's tag vocabulary",
                                 ln.n, m.group(0),
                                 "Allowed: [background noise] [indiscernible] [overlap] [laugh] [cough] "
                                 "[crying] [makes noise] [clears throat] [phonetic] [word?].", "review"))
    return out


# ---------------------------------------------------------------- verbatim protection
# DT KEEPS 'you know' / 'yeah' — nothing to scan; the profile simply must not include the
# GoTranscript scanners that flag them. This scanner exists to catch the OPPOSITE mistake:
# hesitation sounds um/uh must be present in FULL verbatim files (DT default) — a transcript
# of real conversation with ZERO um/uh/uh-huh is a sign they were stripped.
def dt_verbatim_fillers(t: Transcript) -> list[Flag]:
    body = " ".join(ln.text for ln in t.lines).lower()
    words = len(body.split())
    if words > 400 and not re.search(r"\b(um|uh|uh-huh|mm-hmm|hmm)\b", body):
        return [_flag("dt_verbatim", "No hesitation sounds anywhere — verbatim files keep um/uh",
                      t.lines[0].n if t.lines else 1, f"0 fillers in {words} words",
                      "DT default is full verbatim: keep um, uh, offset with commas.", "review")]
    return []


DT_SCANNERS = [
    dt_header, dt_end_of_file, dt_timecodes, dt_speaker_labels, dt_tags, dt_verbatim_fillers,
    legal_dash_form, legal_repeated_words, legal_partial_words,   # shared mechanical checks
]


# ---------------------------------------------------------------- SITE registration
# DT is a SITE plugin (language x field x site): format rules (header, timecodes, labels,
# tags, EOF marker, dash form) are language-NEUTRAL — they govern DT's Spanish files too.
# Only the verbatim-filler heuristic is English-specific.
from .domains import register_site

register_site(
    "dt",
    scanners=(dt_header, dt_end_of_file, dt_timecodes, dt_speaker_labels, dt_tags,
              legal_dash_form, legal_repeated_words, legal_partial_words),
    per_language={"en": (dt_verbatim_fillers,)},
    description="Daily Transcription house format (verbatim, timecoded, DT tag vocabulary)",
)
