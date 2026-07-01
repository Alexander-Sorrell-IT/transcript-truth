"""UMLS medical-terminology verification via the UTS REST API (NLM, licensed).

API-LOOKUP ONLY — the UMLS license restricts redistributing SNOMED/CPT content, so we never bundle
it offline the way we ship public-domain RxNorm. Needs UMLS_API_KEY (env or .env). Lookups are
cached locally (the licensee's own use) to avoid repeat calls.

GRACEFUL: `lookup()` is three-state — a canonical name (found), "" (confirmed NOT in UMLS), or None
(couldn't check: no key / no network / error). The scanner flags ONLY on a confirmed "", so a missing
key or offline run just no-ops — never a false verdict. This is the medical domain's ENGLISH layer
(UMLS is English/US medical), used to VERIFY a term in a clear diagnosis context, not blanket-flag."""
from __future__ import annotations
import os
import json
import urllib.parse
import urllib.request
import re
from .types import Flag, Transcript

_CACHE_PATH = os.path.expanduser("~/.cache/transcript-truth/umls_cache.json")
_API = "https://uts-ws.nlm.nih.gov/rest/search/current"
_cache = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(_CACHE_PATH) as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def _save_cache() -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w") as f:
            json.dump(_cache, f)
    except Exception:
        pass


def _api_key():
    k = os.environ.get("UMLS_API_KEY")
    if k:
        return k.strip()
    # fall back to a .env next to the repo root
    for base in (os.path.dirname(os.path.dirname(__file__)), os.getcwd()):
        p = os.path.join(base, ".env")
        try:
            for line in open(p):
                if line.startswith("UMLS_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            continue
    return None


def lookup(term: str):
    """Return the UMLS canonical name for `term`, "" if confirmed NOT in UMLS, or None if the lookup
    couldn't run (no key / offline / error). Cached."""
    term = (term or "").strip().lower()
    if not term:
        return None
    c = _load_cache()
    if term in c:
        return c[term]
    key = _api_key()
    if not key:
        return None
    try:
        url = _API + "?" + urllib.parse.urlencode({"string": term, "apiKey": key, "pageSize": 1})
        with urllib.request.urlopen(url, timeout=12) as r:
            d = json.load(r)
        res = d.get("result", {}).get("results", [])
        name = res[0]["name"] if res and res[0].get("ui") != "NONE" else ""
        c[term] = name
        _save_cache()
        return name
    except Exception:
        return None                          # couldn't check → caller must no-op, never flag


# Fire only inside a clear diagnosis/condition context, where a following word is very likely a
# medical term — so a word UMLS doesn't recognize there is a probable misspelling (UMLS is
# comprehensive: it has diabetes/hypertension/etc.). Context-gated = high precision.
_DX_CTX = re.compile(
    r"\b(?:diagnosed with|history of|presents with|presenting with|suffers from|"
    r"complains of|complaining of|treated for|consistent with|suggestive of)\s+"
    r"(?:a |an |the |chronic |acute |severe |mild |possible |suspected )?"
    r"([A-Za-z][A-Za-z\-]{5,})", re.I)


def umls_term_check(t: Transcript) -> list[Flag]:
    out: list[Flag] = []
    for ln in t.lines:
        for m in _DX_CTX.finditer(ln.text):
            term = m.group(1)
            name = lookup(term)
            if name == "":                   # confirmed NOT in UMLS (None = couldn't check → skip)
                out.append(Flag(
                    rule="med_umls_term", severity="review", line=ln.n, evidence=term,
                    label=f"Medical: '{term}' not found in UMLS — verify this condition/term",
                    fix=f"'{term}' isn't a recognized UMLS term; check the spelling against the record."))
    return out
