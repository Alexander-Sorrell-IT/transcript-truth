"""Extract the casual/spoken Japanese layer from JMdict — the 'Urban Dictionary'
subset. Transcription is spoken language, so the slang/colloquial/net-slang/abbr/
onomatopoeia-tagged entries matter more than the formal headwords.
"""
import os, sys, json, collections
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = json.load(open(os.path.join(REPO, "data", "jmdict-eng-3.6.2.json"), encoding="utf-8"))

# first: what misc tags actually exist + how many of each
all_tags = collections.Counter()
for w in data["words"]:
    for s in w.get("sense", []):
        for m in s.get("misc", []):
            all_tags[m] += 1

# the casual/spoken-relevant tags
CASUAL = {"col", "sl", "net-sl", "m-sl", "abbr", "on-mim", "joc", "fam", "vulg", "derog", "chn",
          "colloquial", "slang", "internet slang", "abbreviation", "onomatopoeic or mimetic word"}
out, by_tag = [], collections.Counter()
for w in data["words"]:
    kanji = [k["text"] for k in w.get("kanji", [])]
    kana = [k["text"] for k in w.get("kana", [])]
    for s in w.get("sense", []):
        tags = [m for m in s.get("misc", []) if m in CASUAL]
        if not tags:
            continue
        for t in tags:
            by_tag[t] += 1
        out.append({"form": kanji[0] if kanji else (kana[0] if kana else ""),
                    "reading": kana[0] if kana else "",
                    "tags": tags,
                    "gloss": "; ".join(d["text"] for d in s.get("gloss", [])[:3])})

json.dump(out, open(os.path.join(REPO, "data", "jp_colloquial.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"ALL misc tags present in JMdict (top 18):")
for t, c in all_tags.most_common(18):
    print(f"   {t:8} {c}")
print(f"\ncasual/spoken entries extracted -> data/jp_colloquial.json : {len(out)}")
print("by tag:", dict(by_tag.most_common()))
for tag in ["net-sl", "sl", "col", "abbr", "on-mim"]:
    ex = [e for e in out if tag in e["tags"]][:5]
    if ex:
        print(f"\n--- {tag} samples ---")
        for e in ex:
            print(f"   {e['form']}（{e['reading']}） = {e['gloss'][:60]}")
