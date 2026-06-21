#!/usr/bin/env python3
"""Edge-input audit harness: hunt FALSE POSITIVES (spurious flags on correct text)
and FALSE NEGATIVES (real errors uncaught) on the categories named in the task."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import audit_transcript

# (label, text, expectation) — expectation is what a CORRECT auditor should do.
CASES = [
    # ---- proper nouns / place names (these are CORRECT spellings; any flag = FP) ----
    ("propernoun: バルセロナ", "バルセロナでパエリアを食べた。", "no flag (correct loanword place name)"),
    ("propernoun: 九龍", "九龍は香港にある。", "no flag (correct place name)"),
    ("propernoun: ファティマ", "ファティマは聖地として知られている。", "no flag (correct proper noun)"),
    ("propernoun mix: バルセロナ短", "バルセロナ。", "thin fragment, no flag"),

    # ---- numbers / units (correct; any flag = FP) ----
    ("number: 3度", "気温は3度まで下がった。", "no flag"),
    ("number: 8cm", "傷は8cmほどだった。", "no flag"),
    ("number: 150万ドル", "彼は150万ドルを支払った。", "no flag"),
    ("number bare: 3度", "3度", "thin fragment number, no flag"),

    # ---- katakana loanwords (correct; any flag = FP) ----
    ("loanword: コンピューター", "コンピューターが壊れた。", "no flag (correct loanword)"),
    ("loanword bare", "コンピューター", "thin fragment, no flag"),

    # ---- mixed JP / English ----
    ("mixed: API", "APIのレスポンスが遅い。", "no flag"),
    ("mixed: sentence", "I think コンピューター is broken.", "no terminal flag? english+jp"),
    ("mixed: Tokyo", "I visited Tokyo last year.", "english line, terminal . ok"),

    # ---- song-lyric lines (short, often no terminal punctuation) ----
    ("lyric: short JP", "君の声が聞こえる", "lyric, no terminal punct"),
    ("lyric: english", "I will always love you", "lyric line"),
    ("lyric: repeated", "ラララ ラララ", "lyric, double-ish space"),

    # ---- very short fragments (the thin-fragment weakness) ----
    ("frag: はい", "はい。", "single word answer"),
    ("frag: ええ", "ええ", "agreement — NOT filler えー"),
    ("frag: そう", "そう。", "agreement"),
    ("frag: 1 char", "あ", "interjection"),
    ("frag: なんか alone", "なんか。", "filler? or hedge"),
    ("frag: てる", "見てる。", "casual contraction てる"),

    # ---- FALSE-NEGATIVE probes: real errors that SHOULD be caught ----
    ("FN: bad timestamp", "(0:01) こんにちは。", "SHOULD flag timestamp"),
    ("FN: filler um EN", "So um I went home.", "SHOULD flag um"),
    ("FN: jp filler えーと", "えーと、そうですね。", "SHOULD flag えーと"),
    ("FN: homophone 汽車/記者", "記者が事故を起こした。", "wrong-homophone candidate?"),
    ("FN: kana 下さい", "教えて下さい。", "SHOULD flag 下さい->ください"),
    ("FN: exclamation", "すごい！", "SHOULD flag ！"),

    # ---- casual_form substring FP probes ----
    ("FP probe: とく in 解く", "問題を解く。", "解く should NOT be casual とく"),
    ("FP probe: てる in proper", "捨てる。", "捨てる contains てる substring"),
    ("FP probe: っす in word", "りっすん。", "substring っす FP?"),
    ("FP probe: とく in 説く", "道理を説く。", "説く contains とく?"),
]

for label, text, expect in CASES:
    r = audit_transcript(text, mode="clean_verbatim")
    flags = [(f.rule, f.severity, f.evidence, f.label) for f in r.flags]
    print("=" * 70)
    print(f"[{label}]  text={text!r}")
    print(f"  expect: {expect}")
    print(f"  grade={r.grade} score={r.score} nflags={len(r.flags)}")
    for rule, sev, ev, lbl in flags:
        print(f"    -> {rule}/{sev}  ev={ev!r}  | {lbl}")
    if not flags:
        print("    -> (no flags)")
