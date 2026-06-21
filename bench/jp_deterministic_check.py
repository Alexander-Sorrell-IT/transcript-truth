"""RoboTruth principle: no model in the verdict. Deterministic verification.

Stacked deterministic checks on the EXACT transcripts Whisper produced:
  1. OOV   -> SudachiPy says the token isn't a real word (garbled non-words)
  2. RARE  -> wordfreq says it's a real token but vanishingly rare (군島, 子立...)
Content words only (nouns/verbs/adjectives); numbers + particles skipped.
No LLM in the verdict -> can't share the ASR's blind spot.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sudachipy import dictionary, tokenizer
from wordfreq import zipf_frequency

tok = dictionary.Dictionary().create()
C = tokenizer.Tokenizer.SplitMode.C
T = 2.5  # zipf below this = suspiciously rare (zipf: 7=very common, 3=uncommon, 0=absent)
CONTENT = {"名詞", "動詞", "形容詞"}

CLIPS = [
    ("インターネットで敵対的環境コースについて検索すると、おそらく現地企業の住所が出てくるでしょう。",
     "インターネットで敵対的環境コースについて検索するとおそらく現地企業の住所が出てくるでしょう", False),
    ("また、北側に行くなら世界的に有名なマリア像の聖地であるファティマの聖母の聖域、神社を訪れましょう。",
     "また北側に行くなら世界的に有名なマリア像の聖地であるファティマの聖母の聖域神社を訪れましょう", False),
    ("バルセアナの公用語はカタルネ語とスペイン語です。約半数がカタルネ語を好み、大多数がカタルネ語を理解し、ほぼ全員がスペイン語を知っています。",
     "バルセロナの公用語はカタルーニャ語とスペイン語です約半数がカタルーニャ語を好み大多数がカタルーニャ語を理解しほぼ全員がスペイン語を知っています", True),
    ("その長いあごには70本以上の数という葉が並び、甲外には別の子立があり、つまりここを通ったらねぎめちゃはないということになります。",
     "その長い顎には70本以上の鋭い歯が並び口蓋には別の歯列がありつまりここを通ったら逃げ道はないということになります", True),
    ("ロスビー数が小さいほど、時期判定に関して星の活性が低下するわけです。",
     "ロスビー数が小さいほど磁気反転に関して星の活性が低下するわけです", True),
    ("軍島や湖では必ずしもヨットは必要ありません。",
     "群島や湖では必ずしもヨットは必要ありません", True),
]


def numberish(s):
    return any(ch.isdigit() for ch in s)


caught = errtot = fp = 0
for i, (heard, truth, had_err) in enumerate(CLIPS, 1):
    flags = []
    for t in tok.tokenize(heard, C):
        s, pos = t.surface(), t.part_of_speech()[0]
        if pos not in CONTENT or numberish(s):
            continue
        z = zipf_frequency(s, "ja")
        if t.is_oov() or z < T:
            mark = "OOV" if t.is_oov() else f"{z:.1f}"
            flags.append(f"{s}({mark})")
    flagged = bool(flags)
    tag = "ERROR" if had_err else "clean"
    print(f"[{i}] truth={tag:5s} verdict={'FLAG' if flagged else 'pass':4s}  {flags}")
    if had_err:
        errtot += 1; caught += flagged
    elif flagged:
        fp += 1

print(f"\nstacked deterministic check: caught {caught}/{errtot} error clips, {fp} false alarms on {len(CLIPS)-errtot} clean clips")
