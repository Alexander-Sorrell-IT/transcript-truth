"""Medical reference data (the 'more resources' layer) — drug names from RxNorm (NLM, free, no
license). Cached locally; refreshable via the updater (`--refresh-data`), exactly like language
lexicons. The drug-name scanner below flags a word sitting in DOSAGE position that isn't a known
drug and suggests the closest real one — catching the misspelled/wrong drug names that are the
genuine medical-transcription hazard (and the #1 error class in our baseline)."""
from __future__ import annotations
import json
import os
import urllib.request

_CACHE = os.path.expanduser("~/.cache/transcript-truth/rxnorm_drugs.txt")
_RXNAV = "https://rxnav.nlm.nih.gov/REST/displaynames.json"
_DRUGS = None


def refresh_drugs():
    """Download the RxNorm display-name list and cache it. Returns the count, or 0 on failure."""
    try:
        req = urllib.request.Request(_RXNAV, headers={"User-Agent": "transcript-truth"})
        with urllib.request.urlopen(req, timeout=40) as r:
            names = json.load(r).get("displayTermsList", {}).get("term", [])
    except Exception:
        return 0
    names = [n.strip().lower() for n in names if n and n[0].isalpha() and len(n) <= 40]
    os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
    open(_CACHE, "w", encoding="utf-8").write("\n".join(sorted(set(names))))
    global _DRUGS
    _DRUGS = None
    return len(names)


def drug_set():
    """Lazily load the cached drug-name set (empty set if not downloaded yet -> scanner no-ops)."""
    global _DRUGS
    if _DRUGS is None:
        try:
            _DRUGS = set(open(_CACHE, encoding="utf-8").read().split("\n"))
        except Exception:
            _DRUGS = set()
    return _DRUGS
