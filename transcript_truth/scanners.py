"""Deterministic transcription-guideline scanners.

Each scanner: (Transcript) -> list[Flag].  No model, no network — pure regex/rule
hits cited at line. These are the rules that are FULLY deterministic on plain
text (the mechanical half of any transcription style guide). Semantic checks
(right word for the meaning, natural phrasing) are deliberately NOT here — that
is the half a human must verify, and the half that lied to us in Japanese.
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

# A speaker label at the start of a line: "Name:" / "?Name:" (label up to 40 chars, no inner colon)
_SPEAKER = re.compile(r"^\s*(?P<label>[^:]{1,40}?):\s")
# Any timestamp-ish token: [0:00], (00:01:02), [00:01], etc.
_TS_TOKEN = re.compile(r"[\[\(]\s*\d{1,2}:\d{2}(?::\d{2})?\s*[\]\)]")
# The ONE correct shape: [HH:MM:SS] zero-padded, square brackets.
_TS_GOOD = re.compile(r"\[\d{2}:\d{2}:\d{2}\]")
# A correctly-formed inaudible/unintelligible tag.
_INAUD_OK = re.compile(r"\[(inaudible|unintelligible)\s+\d{2}:\d{2}:\d{2}\]")
# Anything that LOOKS like it's trying to be one (catches misspellings + missing ts).
_INAUD_WORDISH = re.compile(
    r"\[\s*(?:in[\s-]?aud\w*|un[\s-]?intel\w*|inaudable|unintelligable|unintellligible)[^\]]*\]",
    re.I,
)
# Clear English fillers removed in Clean Verbatim (conservative — only unambiguous ones).
_CV_FILLERS = re.compile(r"\b(um+|uh+|erm+|uh[-\s]?huh|you know|i mean|kind of|sort of)\b", re.I)
# Japanese つなぎ言葉 removed in Clean Verbatim.
#  CLEAR  = vocalic hesitation, essentially never meaning-bearing -> confident remove.
#  CHECK  = could be a real demonstrative/word (あの=that, その=that, まあ=well) -> surface, human decides.
# Boundary-anchored: a leading (?<![ぁ-ん]) stops the filler matching as the TAIL of a
# real word (へ+えー, ね+え), and a trailing (?![ぁ-ん]) stops it matching as the HEAD of
# one (なんか+い = 何回, まあ+ま = まあまあ). Fillers are hiragana, so "not flanked by more
# hiragana" is the cheap proxy for "standalone hesitation token."
_JP_FILLERS_CLEAR = re.compile(
    r"(?<![ぁ-ん])(えーと|えーっと|えっと|ええと|ええっと|えー|あのー|そのー|うーん|んーと)(?![ぁ-ん])")
_JP_FILLERS_CHECK = re.compile(r"(?<![ぁ-ん])(なんか|まぁ|まあ)(?![ぁ-ん])")
# Full-width sentence-terminal punctuation (what a Japanese line should end on; ！ is banned).
_JP_TERMINAL = "。？」』）】〕"
# Speaker-label form, allowing full-width colon too.
_SPEAKER_JP = re.compile(r"^\s*(?P<label>[^:：]{1,40}?)[：:]\s")
# Exclamation marks (ASCII or full-width) — banned by the guideline.
_BANG = re.compile(r"[!！]")


def timestamps(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _TS_TOKEN.finditer(ln.text):
            tok = m.group(0)
            if not _TS_GOOD.fullmatch(tok.strip()):
                out.append(Flag(
                    rule="timestamps", label="Timestamp not in [HH:MM:SS] form",
                    line=ln.n, severity="moderate", evidence=tok,
                    fix="Square brackets, zero-padded hours/minutes/seconds: [00:09:25].",
                ))
    return out


def speaker_labels(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        m = _SPEAKER.match(ln.text)
        if not m:
            continue
        label = m.group("label").strip()
        if "?" in label and not label.startswith("?"):
            out.append(Flag(
                rule="speaker_labels", label="Uncertain-speaker '?' is misplaced",
                line=ln.n, severity="moderate", evidence=m.group(0).strip(),
                fix="Put '?' BEFORE the whole label: '?Speaker 1:' (not 'Speaker? 1:' / 'Speaker 1?:').",
            ))
    return out


def inaudible(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _INAUD_WORDISH.finditer(ln.text):
            tok = m.group(0)
            if _INAUD_OK.fullmatch(tok):
                continue
            out.append(Flag(
                rule="inaudible", label="Malformed [inaudible]/[unintelligible] tag",
                line=ln.n, severity="moderate", evidence=tok,
                fix="Exactly [inaudible HH:MM:SS] or [unintelligible HH:MM:SS] with a zero-padded timestamp.",
            ))
    return out


def _body(text: str) -> str:
    """Drop a leading speaker label (ASCII or full-width colon) so checks run on speech."""
    m = _SPEAKER_JP.match(text)
    return text[m.end():] if m else text


def fillers(t: Transcript) -> list[Flag]:
    if t.mode != "clean_verbatim":
        return []
    out: list[Flag] = []
    for ln in t.lines:
        body = _body(ln.text)
        for m in _CV_FILLERS.finditer(body):
            out.append(Flag(
                rule="fillers", label=f"Filler '{m.group(0)}' should be removed (Clean Verbatim)",
                line=ln.n, severity="minor", evidence=m.group(0),
                fix="Clean Verbatim drops fillers (um, uh, you know, I mean, kind of, sort of).",
            ))
        for m in _JP_FILLERS_CLEAR.finditer(body):
            out.append(Flag(
                rule="fillers", label=f"つなぎ言葉 '{m.group(0)}' should be removed (Clean Verbatim)",
                line=ln.n, severity="minor", evidence=m.group(0),
                fix="Clean Verbatim drops hesitation fillers (えー・えーと・あのー・うーん…).",
            ))
        for m in _JP_FILLERS_CHECK.finditer(body):
            out.append(Flag(
                rule="fillers", label=f"Possible filler '{m.group(0)}' — remove if not meaning-bearing",
                line=ln.n, severity="minor", evidence=m.group(0),
                fix="なんか/まあ are fillers when hesitation, real words otherwise — you decide.",
            ))
    return out


def spacing(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        s = ln.text.strip()
        if "  " in s or "　　" in s:
            out.append(Flag(rule="spacing", label="Double space", line=ln.n,
                            severity="minor", evidence="  …  ", fix="Use single spaces."))
        # space before punctuation — ASCII or full-width
        sp = re.search(r"\S[ 　]+[,.;:?!、。？！」』）]", ln.text)
        if sp:
            out.append(Flag(rule="spacing", label="Space before punctuation", line=ln.n,
                            severity="minor", evidence=sp.group(0),
                            fix="No space before punctuation (ASCII or full-width)."))
    return out


def no_exclamation(t: Transcript) -> list[Flag]:
    """The guideline bans exclamation marks (ASCII or full-width)."""
    out: list[Flag] = []
    for ln in t.lines:
        if _BANG.search(ln.text):
            out.append(Flag(rule="no_exclamation", label="Exclamation mark not allowed",
                            line=ln.n, severity="moderate", evidence="! / ！",
                            fix="Replace ! / ！ with 。 (period). Exclamation marks are banned."))
    return out


def terminal_punctuation(t: Transcript) -> list[Flag]:
    """Each non-empty speech line should end in 。？ or a closing quote — not bare/comma.
    Exceptions: an interruption '--', a tag line ending in ']'. Only enforced when the
    transcript ACTUALLY uses terminal punctuation somewhere — raw/unpunctuated ASR
    output (e.g. FLEURS) shouldn't be nagged on every line."""
    if not any(c in ln.text for ln in t.lines for c in "。？.?"):
        return []
    out: list[Flag] = []
    for ln in t.lines:
        body = _body(ln.text).rstrip()
        if not body:
            continue
        if body.endswith("--") or body.endswith("]") or body.endswith("-"):
            continue
        if body[-1] in _JP_TERMINAL or body[-1] in ".?。":
            continue
        # plain Japanese/text line that doesn't terminate properly
        out.append(Flag(rule="terminal_punctuation", label="Line does not end with 。？ or closing quote",
                        line=ln.n, severity="minor", evidence="…" + body[-8:],
                        fix="End each sentence with 。 (or ？/」). No bare line-ends or trailing commas."))
    return out


def paragraph_length(t: Transcript) -> list[Flag]:
    """Paragraphs (lines) must be ≤ 250 characters (song-lyric lines excepted)."""
    out: list[Flag] = []
    for ln in t.lines:
        n = len(ln.text.strip())
        if n > 250:
            out.append(Flag(rule="paragraph_length", label=f"Paragraph too long ({n} chars > 250)",
                            line=ln.n, severity="minor", evidence=f"{n} chars",
                            fix="Break paragraphs at ≤250 characters (split at a sentence boundary)."))
    return out


# Japanese semantic/colloquial layers plug in as scanners (they return list[Flag], no-op on English).
from .semantic import homophone_traps          # noqa: E402
from .colloquial import casual_forms            # noqa: E402
from .collocation import suggest_corrections    # noqa: E402
from .verdict import gloss                        # noqa: E402
from .kana_rules import kana_usage                # noqa: E402
from .en_format import en_format                  # noqa: E402
from .language import untranslated_english        # noqa: E402
from .sound_events import sound_event_format       # noqa: E402


def _en(word):
    """word + its English meaning, so a non-Japanese-reader can judge the flag."""
    g = gloss(word)
    return f"{word} ({', '.join(g[:2])})" if g else word


def context_homophones(t: Transcript) -> list[Flag]:
    """The 'does it make sense?' layer: a written word whose same-reading alternative
    fits the sentence's collocations better -> likely the wrong homophone. No model.
    Every flag carries English glosses so it's judgeable without reading Japanese."""
    out: list[Flag] = []
    for ln in t.lines:
        for s in suggest_corrections(_body(ln.text)):
            out.append(Flag(
                rule="context_homophone",
                label=f"{_en(s['written'])} may be wrong here — {_en(s['suggest'])} fits this context",
                line=ln.n, severity="review", evidence=s["written"],
                fix=f"Consider {_en(s['suggest'])} (context-fit {s['suggest_fit']} vs {s['written_fit']}; same sound).",
            ))
    return out


# homophone_traps (blanket "surface every known trap word") is intentionally NOT in the
# default set — it flags correct text too (39 false alarms / 80 clips). context_homophones
# replaces it: it only fires when an alternative actually fits the context better.
ALL_SCANNERS = [
    timestamps, speaker_labels, inaudible, fillers, spacing,
    no_exclamation, terminal_punctuation, paragraph_length,
    casual_forms, context_homophones, kana_usage, en_format,
    untranslated_english, sound_event_format,
]


# --- Thoth fixers for the default profile (Japanese + GoTranscript English) ---
# Only the language-safe mechanical removals. Hesitations (um/uh/erm) are removed
# but NOT the crutch phrases (you know / I mean / kind of / sort of / uh-huh) —
# those are context-dependent (a real "kind of" exists), so they stay flags for a
# human. Exclamation->period is NOT auto-applied here because the right period
# differs by language (. vs 。). NO model — same patterns the scanners detect with.
_CV_FILLERS_FIX = re.compile(r"\b(?:um+|uh+|erm+)\b(?!-)[ ,]*", re.I)
DEFAULT_FIXERS = [
    (_CV_FILLERS_FIX, ""),        # English hesitations
    (_JP_FILLERS_CLEAR, ""),      # Japanese つなぎ言葉 (confident set only)
]


def run_scanners(t: Transcript, scanners=None) -> list[Flag]:
    """Run a scanner set over the transcript. `scanners` defaults to ALL_SCANNERS
    (the original behavior); a profile passes its own tuple of scanner functions."""
    flags: list[Flag] = []
    for s in (ALL_SCANNERS if scanners is None else scanners):
        flags.extend(s(t))
    flags.sort(key=lambda f: (f.line, f.rule))
    return flags
