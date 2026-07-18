"""Japanese deterministic rules. No model in the verdict path.

`japanese_punctuation` — a Japanese clause/sentence uses the full-width 。(kuten) and 、(tōten),
never an ASCII '.'/','. The check fires ONLY when the ASCII mark IMMEDIATELY follows a Japanese
character (kana / kanji / 々 / ー), so it can never touch a decimal (3.14), an English abbreviation
(Mr.), a thousands separator (1,000), or a URL (example.co.jp) — the char before those is a digit or
Latin letter, never Japanese. High-precision by construction.
"""
import re
from .types import Flag, Transcript

# Hiragana, Katakana (+ half-width marks excluded), CJK ideographs, iteration mark 々, chōonpu ー
_JP = r"[぀-ゟ゠-ヿ一-鿿々ー]"
_JP_PERIOD = re.compile(_JP + r"\.")
_JP_COMMA = re.compile(_JP + r",")


def japanese_punctuation(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _JP_PERIOD.finditer(ln.text):
            frag = m.group(0)
            out.append(Flag(rule="ja_punct", label="Japanese sentence should end with 。not ASCII '.'",
                            line=ln.n, severity="minor", evidence=frag,
                            fix=f"Replace the ASCII period after '{frag[0]}' with 。"))
        for m in _JP_COMMA.finditer(ln.text):
            frag = m.group(0)
            out.append(Flag(rule="ja_punct", label="Japanese clause should use 、not ASCII ','",
                            line=ln.n, severity="minor", evidence=frag,
                            fix=f"Replace the ASCII comma after '{frag[0]}' with 、"))
    return out
