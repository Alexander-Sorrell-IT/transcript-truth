#!/usr/bin/env python3
"""Build the multilingual NAME GAZETTEER — the data cell every language needs to reach Japanese's
level (JP has JMnedict's 954k names; this gives the others the same signal). Sources GeoNames
(place names in every language/script via the alternatenames column). Output: data/gazetteer.json
= a flat set of name surfaces (lowercased). The adjudicator looks names up here to tell a real name
from a mishearing, in ANY language — no per-language code, just data (exactly the Japanese pattern).
"""
import os, json, csv, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "geonames", "cities15000.txt")
OUT = os.path.join(ROOT, "data", "gazetteer.json")


def build():
    names = set()
    with open(SRC, encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if len(row) < 4:
                continue
            names.add(row[1].strip().lower())                 # canonical name
            names.add(row[2].strip().lower())                 # ascii name
            for alt in row[3].split(","):                     # every-language alternate names
                alt = alt.strip().lower()
                if alt:
                    names.add(alt)
            # also index each whitespace token of multi-word names (so "New York" matches "york")
    # split multiword names into single tokens too (transcripts are word-by-word)
    toks = set()
    for n in names:
        for t in n.split():
            if len(t) >= 2:
                toks.add(t)
    names |= toks
    names = {n for n in names if n}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(sorted(names), fh, ensure_ascii=False)
    print(f"gazetteer: {len(names)} name surfaces -> {OUT}")


if __name__ == "__main__":
    build()
