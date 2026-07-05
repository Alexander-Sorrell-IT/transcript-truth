#!/usr/bin/env python3
"""Build the multilingual NAME GAZETTEER — the data cell every language needs to reach Japanese's
level (JP has JMnedict's 954k names; this gives the others the same signal). Sources GeoNames
(place names in every language/script via the alternatenames column). Output: data/gazetteer.json
= a flat set of name surfaces (lowercased). The adjudicator looks names up here to tell a real name
from a mishearing, in ANY language — no per-language code, just data (exactly the Japanese pattern).
"""
import os, json, csv, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "geonames", "cities500.txt")   # every place pop>=500, all scripts
OUT = os.path.join(ROOT, "data", "gazetteer.json")


def person_names():
    """730k given + 983k family names (names-dataset). This catches 'Kagiso' the PERSON —
    GeoNames only has places, and JMnedict's edge over the old gazetteer was exactly people."""
    try:
        from names_dataset import NameDataset
        nd = NameDataset()
        return {n.lower() for n in nd.first_names} | {n.lower() for n in nd.last_names}
    except Exception as e:
        print(f"names-dataset unavailable ({e}) — building places-only", file=sys.stderr)
        return set()


def build():
    names = person_names()
    print(f"person names: {len(names)}")
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
