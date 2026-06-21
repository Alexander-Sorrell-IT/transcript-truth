"""Sound-event normalization to the GoTranscript guideline format: non-speech sounds in
[brackets], lowercase, present tense, <=2 words. Two inputs: (1) parenthetical annotations
the models emit — Gemini/Scribe write "(laughs)", "(music)" — normalized to [laughs];
(2) Japanese non-lexical vocalizations (ふん=scoff, しっ=shushing, はぁ=sigh) mapped to the
bracket tag. Deterministic. Pairs with the `sound_event_format` scanner.
"""
import re

# Japanese non-lexical vocalizations -> guideline sound-event tag (present tense, lowercase).
_VOCAL = {
    "ふーん": "[scoffs]", "ふん": "[scoffs]", "フン": "[scoffs]", "フーン": "[scoffs]",
    "しーっ": "[shushing]", "シーッ": "[shushing]", "しっ": "[shushing]", "シッ": "[shushing]",
    "はぁ": "[sighs]", "はあ": "[sighs]", "ハァ": "[sighs]", "ふぅ": "[sighs]",
    "あはは": "[laughs]", "あははは": "[laughs]", "ははは": "[laughs]", "ハハハ": "[laughs]",
    "ふふ": "[chuckles]", "えへへ": "[chuckles]", "くすくす": "[chuckles]",
}
# Parenthetical annotations the ASR models emit -> bracketed lowercase.
_PAREN = re.compile(r"[（(]\s*(laughs?|laughter|sighs?|coughs?|chuckles?|gasps?|applause|"
                    r"music|background noise|crosstalk|grunts?|scoffs?)\s*[)）]", re.I)


def normalize_sounds(text):
    text = _PAREN.sub(lambda m: "[" + m.group(1).lower() + "]", text)
    for k, v in _VOCAL.items():
        text = re.sub(rf"(?<![ァ-ヶ]){k}[。、！]?", v, text)
    return re.sub(r"\[\s+", "[", text)


def sound_event_format(t):
    """Flag sound notations in ( ) instead of [ ], and un-bracketed known vocalizations."""
    from .types import Flag
    out = []
    for ln in t.lines:
        for m in _PAREN.finditer(ln.text):
            out.append(Flag(rule="sound_event", severity="moderate", line=ln.n, evidence=m.group(0),
                            label=f'sound event "{m.group(0)}" must use [ ] lowercase, e.g. [{m.group(1).lower()}]',
                            fix="Sound events use square brackets, lowercase, present tense."))
        for k, v in _VOCAL.items():
            if re.search(rf"(?<![ァ-ヶ]){k}[。、！]?", ln.text):
                out.append(Flag(rule="sound_event", severity="review", line=ln.n, evidence=k,
                                label=f'"{k}" is a sound, not speech — render as {v}', fix=f"Use {v}."))
    return out
