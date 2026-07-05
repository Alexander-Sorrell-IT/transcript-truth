"""Deterministic word-level adjudicator — the 'brain' that lets the consensus DECIDE, not just vote.

Given the candidate words the witnesses proposed for ONE position, plus the sentence context, score
each by deterministic linguistic validity — is it a real word (lexicon), does it fit its neighbours
(collocation) — and return the best candidate + a confidence margin. This lets the consensus pick a
linguistically-correct MINORITY word over a mediocre majority (the whole 'models propose, code
decides' thesis, applied to word choice), instead of deciding by vote-count/centrality alone.

NEVER invents: it only ranks words a real witness already proposed. Reuses lexicon (word validity,
multilingual) + decision collocations (context fit: en/es/ru/uk/jp). For languages/words with no
lexical signal (e.g. rare proper nouns absent from every dictionary) it returns low confidence, so
the caller falls back to the vote — it helps where it has signal, stays silent where it doesn't.
"""
import os, json, functools, unicodedata
from . import lexicon
from . import decision as _dec

_STRIP = ".,!?;:'\"()[]«»„“”…-—"
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@functools.lru_cache(maxsize=1)
def gazetteer():
    """Multilingual NAME gazetteer (place/person/org surfaces in every language & script, from
    GeoNames — build with bench/build_gazetteer.py). This is the data cell that gives EVERY language
    the name signal Japanese gets from JMnedict, so the brain can tell a real name ('Marsilya',
    'München', 'Мюнхен') from a mishearing in any language. Empty set if not built yet (graceful)."""
    try:
        return set(json.load(open(os.path.join(_DATA, "gazetteer.json"), encoding="utf-8")))
    except Exception:
        return set()


def _clean(w):
    """Lowercase + strip punctuation, robust to casing artifacts. Turkish dotted-İ lowercases to
    'i' + a combining dot (U+0307) which no wordlist matches; drop that stray mark so 'İstanbul'
    normalizes to 'istanbul'. NFC-normalize so composed/decomposed forms compare equal."""
    s = unicodedata.normalize("NFC", w.strip(_STRIP).lower().replace("̇", ""))
    return s


# Web-frequency floor for the proper-noun tier. Real names ("Kagiso" zipf~1.6, "Reykjavik" ~2.8)
# clear it; mis-heard non-words ("Cogizzo", "Njorog") score 0.0 (they appear nowhere). wordfreq
# covers every language we support, so this gives PROPER-NOUN parity with no per-language gazetteer.
_NAME_FLOOR = 1.0


def _is_known(word, lang):
    """Dictionary-valid (a correctly-spelled real word OR a known name) in `lang`. Japanese uses its
    native authoritative data — JMdict (words) + JMnedict (954k name surfaces) via verdict — which is
    richer than any frequency signal; every other language uses its lexicon backend."""
    w = _clean(word)
    if not w:
        return False
    raw = word.strip(_STRIP)
    if lang in ("ja", "jp"):
        try:
            from . import verdict
            if verdict.gloss(raw) is not None or raw in verdict.name_index():
                return True
        except Exception:
            pass
    # multilingual NAME gazetteer — the data cell that gives every language JP-level name recognition
    g = gazetteer()
    if w in g or raw.lower() in g:
        return True
    try:
        return bool(lexicon.is_known(w, lang))
    except Exception:
        return False


def _zipf(word, lang):
    """Web-corpus frequency (0.0 if unseen / unavailable). Distinguishes a real name that appears
    in text from a mis-heard non-word that appears nowhere."""
    w = _clean(word)
    if not w:
        return 0.0
    try:
        from wordfreq import zipf_frequency
        return zipf_frequency(w, lang)
    except Exception:
        return 0.0


def _validity(word, lang):
    """Kept for callers/tests: 1.0 if dictionary-valid OR a frequent real name, else 0.0. The
    per-position decision in adjudicate() uses the sharper two-tier rule below, not this union."""
    return 1.0 if (_is_known(word, lang) or _zipf(word, lang) >= _NAME_FLOOR) else 0.0


def _fit(word, context, lang):
    """How many of `word`'s expected collocates appear in the context (0 if no data)."""
    try:
        col = _dec._colloc(lang)
    except Exception:
        col = {}
    if not col:
        return 0.0
    comp = set(col.get(_clean(word), []))
    ctx = {_clean(c) for c in context}
    return float(len(comp & ctx))


def score(word, context, lang):
    """Deterministic linguistic score: validity is primary (real word), collocation fit is only a
    secondary ordering nudge AMONG equally-valid words — it never drives an override by itself."""
    return _validity(word, lang) + 0.5 * _fit(word, context, lang)


def adjudicate(candidates, context, lang):
    """candidates: proposed surfaces for one position. context: neighbours. Returns
    (best_surface, confidence). Confidence is 1.0 only when the judge can cleanly separate a real
    word/name from a mis-heard non-word; 0.0 otherwise (caller then defers to the vote).

    TWO-TIER rule (this is what keeps names in but misspellings out):
      TIER 1 — dictionary: if SOME candidates are correctly-spelled real words and some aren't,
        pick the best real word (fit breaks ties). Handles misspellings ('their' beats 'thier',
        because 'thier' — however frequent — is not a dictionary word while 'their' is).
      TIER 2 — proper nouns: only when NO candidate is a dictionary word (real names aren't in
        fixed dictionaries), use web frequency — a name appears in text, a mishearing scores 0.
        ('Kagiso' beats 'Cogizzo'.) If all are dictionary-valid, or all are equally name-like /
        equally unseen, confidence is 0.0 — never rewrite one valid word into another."""
    uniq, seen = [], set()
    for c in candidates:
        k = _clean(c)
        if k and k not in seen:
            seen.add(k); uniq.append(c)
    if not uniq:
        return "", 0.0

    known = {c: _is_known(c, lang) for c in uniq}
    n_known = sum(known.values())
    # TIER 1 — dictionary separates them
    if 0 < n_known < len(uniq):
        valid = [c for c in uniq if known[c]]
        best = max(valid, key=lambda c: _fit(c, context, lang))
        return best, 1.0
    if n_known == len(uniq):
        return uniq[0], 0.0                       # all valid dictionary words -> defer to vote

    # TIER 2 — none are dictionary words (proper-noun territory) -> web frequency separates them.
    # ONLY act on the unambiguous case: exactly ONE candidate appears in web text (a real name) and
    # every other is unseen (a mishearing). If two+ candidates are plausible names, frequency can't
    # say which was actually spoken (higher-frequency != correct — 'Jorg' is commoner than the
    # correct-but-rarer 'Njoroge'), so we defer to the vote rather than pick the more common name.
    freq = {c: _zipf(c, lang) for c in uniq}
    above = [c for c in uniq if freq[c] >= _NAME_FLOOR]
    if len(above) == 1:
        return above[0], 1.0
    return uniq[0], 0.0                            # ambiguous names / all unseen -> defer
