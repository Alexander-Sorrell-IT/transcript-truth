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
        tmp = _CACHE_PATH + ".tmp"                # atomic write: temp + rename, so a concurrent
        with open(tmp, "w") as f:                 # reader never sees a half-written (corrupt) file
            json.dump(_cache, f)
        os.replace(tmp, _CACHE_PATH)
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


# Diagnosis/condition CONTEXT phrases per language — the one language-specific piece. The medical
# domain is built ONCE; each language contributes its trigger phrases so the SAME (multilingual) UMLS
# verifier works across the language plugins. UMLS resolves native terms in all these languages
# (verified: neumonía→Pneumonia, diabète→Diabetes, Lungenentzündung→Pneumonitis). Add a language by
# adding one row — no separate "Spanish medical" build. Languages absent here simply no-op (safe).
_DX_PHRASES = {
    "en": ("diagnosed with", "history of", "presents with", "presenting with", "suffers from",
           "complains of", "complaining of", "treated for", "consistent with", "suggestive of"),
    "es": ("diagnosticado con", "diagnosticada con", "antecedentes de", "historia de", "presenta",
           "refiere", "tratado por", "tratada por", "compatible con"),
    "fr": ("diagnostiqué avec", "diagnostiquée avec", "antécédents de", "présente", "souffre de",
           "traité pour", "traitée pour", "compatible avec"),
    "de": ("diagnostiziert mit", "anamnese von", "leidet an", "behandelt wegen", "verdacht auf"),
    "pt": ("diagnosticado com", "diagnosticada com", "histórico de", "apresenta", "tratado para",
           "tratada para", "compatível com"),
    "it": ("diagnosticato con", "diagnosticata con", "storia di", "presenta", "soffre di",
           "trattato per", "trattata per", "compatibile con"),
}
# capture-boundary words (a mix across the covered languages) — only truncate the captured phrase;
# the head-noun fallback is the real safety net, so over/under-capture never causes a false positive.
_BOUNDARY = (r"(?=[.,;:!?]|\s+(?:and|or|but|since|with|after|before|for|in|on|at|this|that|today|"
             r"yesterday|now|currently|recently|per|y|e|o|et|ou|und|oder|mit|seit|con|di|du|des)\b|$)")
_dx_cache = {}


def _dx_regex(lang):
    """Per-language diagnosis-context regex (cached). None if we have no phrases for this language."""
    if lang not in _dx_cache:
        phrases = _DX_PHRASES.get(lang)
        _dx_cache[lang] = re.compile(
            r"(?:" + "|".join(re.escape(p) for p in phrases) + r")\s+"
            r"(?:a |an |the |un |una |el |la |le |les |der |die |das |o |uma )?"
            r"([^\s.,;:!?][^.,;:!?\n]{2,45}?)" + _BOUNDARY, re.I) if phrases else None
    return _dx_cache[lang]


def _freq(word, lang):
    """word-frequency (zipf) in `lang`, falling back to English; 0.0 if wordfreq is unavailable."""
    try:
        from wordfreq import zipf_frequency, available_languages
        return zipf_frequency(word, lang if lang in available_languages() else "en")
    except Exception:
        return 0.0


def umls_term_check(t: Transcript) -> list[Flag]:
    """Verify a diagnosis-context term against UMLS, in the transcript's OWN language. Built once;
    works for every language with a phrase row above, reusing that language plugin. Graceful."""
    lang = getattr(t, "lang", "en") or "en"
    rx = _dx_regex(lang)
    if rx is None:                                    # no trigger phrases for this language → no-op
        return []
    out: list[Flag] = []
    for ln in t.lines:
        for m in rx.finditer(ln.text):
            phrase = m.group(1).strip()
            words = phrase.split()
            head = words[-1] if words else ""
            if len(head) < 5:                        # too short to be a checkable condition head
                continue
            # a COMMON word (in this language) is not a medical misspelling — it's ordinary speech that
            # merely followed "history of"/"presents with" ("...history of arriving unannounced"). Skip
            # it. Misspellings sit at zipf ~0; every everyday word is ≥3.0. This is the no-FP guard.
            if _freq(head.lower(), lang) >= 3.0:
                continue
            name = lookup(phrase)                    # try the whole phrase first
            if name is None:                         # couldn't check (no key/offline/error) → no flag
                continue
            if name == "":                           # phrase not in UMLS — fall back to the head noun
                hname = lookup(head)                 # so "pneumonia yesterday" → head "pneumonia" clears
                if hname == "":                      # BOTH not found → likely a real misspelling
                    out.append(Flag(
                        rule="med_umls_term", severity="review", line=ln.n, evidence=phrase,
                        label=f"Medical: '{phrase}' not found in UMLS — verify this condition/term",
                        fix=f"'{phrase}' isn't a recognized UMLS term; check the spelling against the record."))
    return out
