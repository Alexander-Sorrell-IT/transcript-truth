"""Deterministic kana-usage rules (GoTranscript guideline rule 24): formal nouns and
faded auxiliaries must be written in kana, not kanji. No model.

  形式名詞:   そんな訳 -> そんなわけ,  歩く事 -> 歩くこと,  雨の為 -> 雨のため
  補助動詞:   教えて下さい -> ください,  使って見る -> みる,  置いて置く -> おく
  準体助詞:   医者と言う -> という

Detection is grammatical (Sudachi), so 翻訳 / 事件 / 映画を見る / 物を置く are NOT flagged.
"""
import os
from sudachipy import dictionary, tokenizer
from .types import Flag, Transcript

_tok = dictionary.Dictionary().create()
_C = tokenizer.Tokenizer.SplitMode.C

# formal nouns with no real standalone usage -> always kana when standalone
_FORMAL_ALWAYS = {"為": "ため", "筈": "はず"}
# formal nouns that also exist as real words -> kana only when modified by a 連体 form / の
_FORMAL_GUARDED = {"訳": "わけ", "事": "こと", "所": "ところ", "時": "とき"}
_GUARD_POS = {"動詞", "形容詞", "形状詞", "連体詞", "助動詞"}
# faded auxiliaries (by lemma) -> kana, but only after a て/で-form
_AUX_TE = {"頂く": "いただく", "見る": "みる", "行く": "いく", "置く": "おく",
           "来る": "くる", "貰う": "もらう", "付く": "つく", "下さる": "くださる",
           "仕舞う": "しまう", "居る": "いる"}


def _flag(surf, kana, line, why):
    # rule-24 kana violations are OBJECTIVE guideline errors (high-precision, 0 FP on
    # the guideline fixtures) -> moderate so they actually move the grade.
    return Flag(rule="kana_usage", label=f"'{surf}' should be kana '{kana}' ({why})",
                line=line, severity="moderate", evidence=surf,
                fix=f"Write {surf} as {kana} — {why}.")


def kana_usage(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        ms = _tok.tokenize(ln.text, _C)
        for i, m in enumerate(ms):
            s = m.surface()
            prev = ms[i - 1] if i > 0 else None
            # --- 補助動詞: 下さい always; others only after て/で ---
            if s in ("下さい", "下さ"):
                out.append(_flag(s, "ください", ln.n, "polite auxiliary"))
                continue
            lemma = m.dictionary_form()
            if lemma in _AUX_TE and prev is not None and prev.surface() in ("て", "で"):
                out.append(_flag(s, _AUX_TE[lemma] if lemma == s else s + "→" + _AUX_TE[lemma],
                                 ln.n, "faded auxiliary verb"))
                continue
            # --- 準体助詞: と言う -> という ---
            if lemma == "言う" and prev is not None and prev.surface() == "と":
                out.append(_flag(s, "いう", ln.n, "quotative という"))
                continue
            # --- 形式名詞 ---
            if s in _FORMAL_ALWAYS:
                out.append(_flag(s, _FORMAL_ALWAYS[s], ln.n, "formal noun"))
            elif s in _FORMAL_GUARDED and prev is not None and (
                    prev.part_of_speech()[0] in _GUARD_POS or prev.surface() == "の"):
                out.append(_flag(s, _FORMAL_GUARDED[s], ln.n, "formal noun"))
    return out
