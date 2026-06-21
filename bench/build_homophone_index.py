"""More information about Japanese, layer-2 fuel: group EVERY common JMdict word by
its READING, attach frequency, so identical-sound words can be RANKED instead of
just called 'ambiguous'. This is the data that turns 'human decides' into
'likely X, runner-up Y' for most homophone collisions."""
import json, glob, os, collections
from sudachipy import dictionary, tokenizer

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from wordfreq import zipf_frequency
    HAVE_FREQ = True
except Exception:
    HAVE_FREQ = False

f = sorted(glob.glob(os.path.join(DIR, "data", "*jmdict*common*")))[0]
words = json.load(open(f))["words"]

# reading (katakana) -> list of {word, glosses, zipf}
by_reading = collections.defaultdict(list)
for w in words:
    glosses = []
    for s in w["sense"]:
        glosses += [g["text"] for g in s.get("gloss", [])]
    kanji = [k["text"] for k in w.get("kanji", [])]
    kana = [k["text"] for k in w.get("kana", [])]
    if not kanji or not kana:
        continue
    read = kana[0]
    for kw in kanji:
        z = zipf_frequency(kw, "ja") if HAVE_FREQ else 0.0
        by_reading[read].append({"word": kw, "zipf": round(z, 2), "gloss": glosses[:3]})

# keep only readings with >=2 distinct real words = the homophone-collision space
homophones = {r: sorted(v, key=lambda x: -x["zipf"])
              for r, v in by_reading.items()
              if len({x["word"] for x in v}) >= 2}

out = os.path.join(DIR, "data", "jp_homophones_by_reading.json")
json.dump(homophones, open(out, "w"), ensure_ascii=False, indent=0)

print(f"frequency data available: {HAVE_FREQ}")
print(f"total common JMdict words indexed : {len(words)}")
print(f"distinct readings                 : {len(by_reading)}")
print(f"readings with >=2 real words (homophone sets): {len(homophones)}")
print(f"saved -> {out}")
# show a few real collisions with their frequency ranking
print("\nsample homophone sets (ranked by frequency):")
shown = 0
for r in ("グントウ", "ボウエキショウ", "ジキ", "コウガイ", "シリツ"):
    if r in homophones:
        opts = " | ".join(f"{x['word']}({x['zipf']}: {x['gloss'][0] if x['gloss'] else '?'})" for x in homophones[r][:4])
        print(f"  {r}: {opts}")
        shown += 1
