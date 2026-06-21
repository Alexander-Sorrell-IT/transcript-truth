"""Per-segment language detection (deterministic, by script). Splits a mixed
Japanese/English line into same-language runs so each run can be routed to the
right verification catalog: Japanese runs -> kana/JP-homophone/coherence checks,
English runs -> EN-homophone/formatting checks. No model.
"""
import re

_JP = re.compile(r"[぀-ヿ一-鿿々〆ー]")   # hiragana, katakana, kanji, ー
_LATIN = re.compile(r"[A-Za-z]")


def lang_of(text):
    """'ja' if the text is mostly Japanese script, 'en' if mostly Latin, else 'mixed'."""
    j = len(_JP.findall(text))
    e = len(_LATIN.findall(text))
    if j and j >= e:
        return "ja"
    if e and e > j:
        return "en"
    return "ja" if j else "en" if e else "neutral"


_KATA_RUN = re.compile(r"[ァ-ヶ][ァ-ヶー・]{6,}")  # katakana run >= 7 chars

# Short katakana that are conversational English, not Japanese content. CLEAR = essentially
# never used as a Japanese word -> flag anywhere. CHECK = also a real loanword (ライト=light) ->
# only flag in a bilingual line (English present), so monolingual JP files don't false-fire.
_KATA_EN_CLEAR = {"オーマイゴッド": "Oh my God", "オーマイガッド": "Oh my God", "サンキュー": "thank you",
                  "ハロー": "hello", "ハロウ": "hello", "ソーリー": "sorry", "プリーズ": "please",
                  "イエス": "yes", "ウェル": "well", "ファニー": "funny"}
_KATA_EN_CHECK = {"ライト": "Right", "グッド": "good", "ナイス": "nice", "ノー": "no",
                  "オーケー": "okay", "オッケー": "okay", "イングリッシュ": "English", "ムービー": "movie"}


def untranslated_english(t):
    """Flag katakana that's really spoken English, not Japanese — both long non-dictionary
    runs (アイラブディスムービー) and short conversational ones (オーマイゴッド, ライト).
    Deterministic, so it catches what the stitching model misses. Real loanwords are guarded:
    dictionary words for long runs, bilingual-context gate for short ones."""
    from .verdict import gloss
    from .types import Flag
    out = []
    for ln in t.lines:
        for m in _KATA_RUN.finditer(ln.text):
            run = m.group(0)
            if not gloss(run):
                out.append(Flag(
                    rule="untranslated_english", severity="review", line=ln.n, evidence=run,
                    label=f'long katakana "{run[:24]}" — likely English spoken, transcribe as English',
                    fix="Replace katakana-English with the actual English words from the English-mode read."))
        has_en = bool(_LATIN.search(ln.text))  # bilingual line?
        for kata, eng in _KATA_EN_CLEAR.items():
            if kata in ln.text:
                out.append(Flag(rule="untranslated_english", severity="review", line=ln.n, evidence=kata,
                    label=f'"{kata}" is spoken English — transcribe as "{eng}"', fix=f'Write "{eng}".'))
        if has_en:
            for kata, eng in _KATA_EN_CHECK.items():
                if kata in ln.text:
                    out.append(Flag(rule="untranslated_english", severity="review", line=ln.n, evidence=kata,
                        label=f'"{kata}" may be spoken English "{eng}" (bilingual line) — verify',
                        fix=f'If spoken in English, write "{eng}".'))
    return out


def segments(text):
    """Split text into consecutive (lang, run) chunks at script boundaries. Punctuation
    and spaces attach to the surrounding run so runs stay readable."""
    out = []
    cur_lang, cur = None, ""
    for ch in text:
        if _JP.search(ch):
            l = "ja"
        elif _LATIN.search(ch):
            l = "en"
        else:
            l = None  # punctuation/space/digit -> stick with current run
        if l is None or l == cur_lang or cur_lang is None:
            cur += ch
            if l is not None:
                cur_lang = cur_lang or l
        else:
            out.append((cur_lang, cur))
            cur, cur_lang = ch, l
    if cur:
        out.append((cur_lang or "neutral", cur))
    # merge tiny neutral-only trailing bits handled implicitly; coalesce same-lang neighbours
    merged = []
    for lang, run in out:
        if merged and merged[-1][0] == lang:
            merged[-1] = (lang, merged[-1][1] + run)
        else:
            merged.append((lang, run))
    return merged
