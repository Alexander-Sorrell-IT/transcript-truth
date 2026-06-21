"""Download Japanese text and build a deterministic word-pair (collocation) table:
for each content word, which words co-occur next to it. This is the no-AI context
signal -- 群島 sits next to 湖/海/島; 軍島 sits next to nothing. Pure counting.

Streams Japanese Wikipedia (no full download), Sudachi-tokenizes, counts adjacent
content-word bigrams, saves the top co-occurrences per word to data/jp_collocations.json.
"""
import os, sys, json, collections, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datasets import load_dataset
from sudachipy import dictionary, tokenizer

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DIR, "data", "jp_collocations.json")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "8000"))
MAX_SECONDS = int(os.environ.get("MAX_SECONDS", "1200"))

_tok = dictionary.Dictionary().create()
_MODE = tokenizer.Tokenizer.SplitMode.C
_CONTENT = {"名詞", "動詞", "形容詞"}  # nouns, verbs, adjectives

def content_words(text):
    out = []
    for m in _tok.tokenize(text, _MODE):
        if m.part_of_speech()[0] in _CONTENT and len(m.surface()) > 1:
            out.append(m.surface())
    return out

print("streaming Japanese Wikipedia...", flush=True)
ds = load_dataset("wikimedia/wikipedia", "20231101.ja", split="train", streaming=True)

pair = collections.Counter()
start = time.time()
n = 0
for art in ds:
    if n >= MAX_ARTICLES or time.time() - start > MAX_SECONDS:
        break
    words = content_words(art["text"][:4000])  # cap per-article work
    for a, b in zip(words, words[1:]):
        if a != b:
            pair[(a, b)] += 1
    n += 1
    if n % 1000 == 0:
        print(f"  {n} articles, {len(pair)} distinct pairs, {int(time.time()-start)}s", flush=True)

# collapse to: word -> top co-occurring neighbours (both directions)
neigh = collections.defaultdict(collections.Counter)
for (a, b), c in pair.items():
    if c >= 2:
        neigh[a][b] += c
        neigh[b][a] += c
out = {w: [x for x, _ in c.most_common(20)] for w, c in neigh.items() if sum(c.values()) >= 3}
json.dump(out, open(OUT, "w"), ensure_ascii=False)
print(f"\nDONE: {n} articles -> {len(out)} words with collocations -> {OUT}", flush=True)
# spot check
for w in ("群島", "磁気", "参列"):
    if w in out:
        print(f"  {w}: {out[w][:8]}")
