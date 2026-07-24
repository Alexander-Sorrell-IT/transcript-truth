#!/usr/bin/env python3
"""Fetch the optional FULL JMdict (~117MB unzipped) from jmdict-simplified releases.

The repo BUNDLES data/jmdict-eng-common-*.json (16MB) + data/jp_name_surfaces.json (JMnedict
954k name surfaces), so Japanese works with zero fetches; verdict.gloss_index prefers the full
dictionary when present (better rare-word coverage), which is what this script installs.
Idempotent: skips if a full jmdict-eng file already exists. Never raises — a failed fetch just
leaves the bundled fallback in place (setup.sh treats any exit as soft).

JMdict/JMnedict © EDRDG (CC BY-SA 4.0) via github.com/scriptin/jmdict-simplified.
"""
import glob
import io
import json
import os
import re
import sys
import urllib.request
import zipfile

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"


def main():
    full = [p for p in glob.glob(os.path.join(DATA, "*jmdict*eng*")) if "common" not in p]
    if full:
        print(f"   [ok] full JMdict present: {os.path.basename(full[0])}")
        return 0
    try:
        with urllib.request.urlopen(API, timeout=30) as r:
            assets = json.load(r).get("assets", [])
        # the full English dictionary asset, NOT the -common- slice: jmdict-eng-3.x.y+date.json.zip
        cand = [a for a in assets
                if re.match(r"jmdict-eng-\d[\w.+-]*\.json\.zip$", a["name"])
                and "common" not in a["name"]]
        if not cand:
            print("   [!!] no full jmdict-eng asset in the latest release"); return 1
        url, name = cand[0]["browser_download_url"], cand[0]["name"]
        print(f"   downloading {name} ...")
        with urllib.request.urlopen(url, timeout=600) as r:
            buf = io.BytesIO(r.read())
        with zipfile.ZipFile(buf) as z:
            member = next(m for m in z.namelist() if m.endswith(".json"))
            z.extract(member, DATA)
        print(f"   [ok] {member} -> data/")
        return 0
    except Exception as e:
        print(f"   [!!] fetch failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
