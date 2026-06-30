"""Deterministic rules for non-Latin-script languages (Arabic, Urdu, Hindi).

- tatweel: the kashida ـ (U+0640) is a decorative letter-elongation, never meaning-bearing —
  it must not appear in a clean transcript. High-confidence, model-free (Arabic/Urdu).
- make_latin_leak: in a line that is predominantly native script, a run of Latin letters is
  usually an untranslated/transliterated leak — surfaced for review (script-agnostic factory).
"""
from __future__ import annotations
import re
from .types import Flag, Transcript

_TATWEEL = "ـ"
_LATIN_RUN = re.compile(r"[A-Za-z]{2,}")


def tatweel(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        if _TATWEEL in ln.text:
            out.append(Flag(
                rule="tatweel", label="Tatweel (kashida ـ) — decorative elongation, remove it",
                line=ln.n, severity="minor", evidence="ـ",
                fix="Delete the kashida ـ; it carries no meaning and doesn't belong in a transcript."))
    return out


def make_latin_leak(native_re, lang_name):
    """Factory: flag Latin-script words inside a line that is mostly `native_re` script —
    likely an untranslated word to verify. `native_re` is a compiled regex matching one
    native-script char."""
    def latin_leak(t: Transcript) -> list[Flag]:
        out: list[Flag] = []
        for ln in t.lines:
            native = len(native_re.findall(ln.text))
            latin = len(re.findall(r"[A-Za-z]", ln.text))
            if native >= 3 and native > latin:        # a genuinely native-script line
                for m in _LATIN_RUN.finditer(ln.text):
                    out.append(Flag(
                        rule="latin_leak", severity="review", line=ln.n, evidence=m.group(0),
                        label=f"Latin word '{m.group(0)}' in {lang_name} text — verify (untranslated?)",
                        fix="Transcribe in-language unless it's a genuine proper noun/term."))
        return out
    latin_leak.__name__ = f"latin_leak_{lang_name.lower()}"
    return latin_leak
