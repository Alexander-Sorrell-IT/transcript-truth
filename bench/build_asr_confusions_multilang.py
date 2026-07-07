#!/usr/bin/env python3
"""Mine EMPIRICAL per-language ASR-confusion tables from the parity bench's saved reads —
the JA-only cell (jp_asr_confusions.json), generalized. For every clip and every witness:
align read vs ground truth; each 1:1 'replace' token pair is a real confusion (gold -> heard)
that model actually made in that language. Free: reads are cached in bench/full_parity.json.

-> data/<lang>_asr_confusions.json  {"_meta": {...}, "confusions": {gold: [[heard, count], ...]}}
Reruns as the battery grows — the table sharpens with every new measured clip."""
import os, sys, json, glob, difflib, collections, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_WORD = re.compile(r"[\w']+", re.UNICODE)


def toks(s):
    return _WORD.findall(s.lower())


rows = json.load(open(os.path.join(ROOT, "bench", "full_parity.json"), encoding="utf-8"))
by_lang = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
clips = collections.Counter()
for r in rows:
    ref_path = os.path.join(ROOT, "bench", "battery", r["clip"])
    gold = toks(json.load(open(ref_path, encoding="utf-8"))["text"])
    clips[r["lang"]] += 1
    for model, read in r["reads"].items():
        heard = toks(read)
        sm = difflib.SequenceMatcher(a=gold, b=heard, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "replace" and (i2 - i1) == (j2 - j1):
                for k in range(i2 - i1):
                    g, h = gold[i1 + k], heard[j1 + k]
                    if g != h:
                        by_lang[r["lang"]][g][h] += 1

for lang, conf in sorted(by_lang.items()):
    table = {g: sorted(([h, c] for h, c in hs.items()), key=lambda x: -x[1])
             for g, hs in conf.items()}
    out = {"_meta": {"clips": clips[lang], "pairs": sum(len(v) for v in table.values())},
           "confusions": table}
    path = os.path.join(ROOT, "data", f"{lang}_asr_confusions.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"{lang}: {out['_meta']['pairs']} confusion pairs from {clips[lang]} clips")
