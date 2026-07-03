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
from . import lexicon
from . import decision as _dec

_STRIP = ".,!?;:'\"()[]«»„“”…-—"


def _clean(w):
    return w.strip(_STRIP).lower()


def _validity(word, lang):
    """1.0 if a real word in `lang`, else 0.0 (graceful 0.0 if the backend is unavailable)."""
    w = _clean(word)
    if not w:
        return 0.0
    try:
        return 1.0 if lexicon.is_known(w, lang) else 0.0
    except Exception:
        return 0.0


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
    (best_surface, confidence). CONFIDENCE IS A VALIDITY MARGIN ONLY: it's high only when the best
    candidate is a real word and the runner-up is NOT. Collocation fit orders among equally-valid
    words but can never trigger an override on its own — so the judge promotes a real word over a
    mis-heard non-word, but never rewrites one valid word into another (that would 'correct' the
    speaker's actual phrasing, e.g. 'waiting on' -> 'waiting for'). Homophone-among-valid-words is
    left to the review-tier scanners, not silently changed here."""
    uniq, seen = [], set()
    for c in candidates:
        k = _clean(c)
        if k and k not in seen:
            seen.add(k); uniq.append(c)
    if not uniq:
        return "", 0.0
    # rank by (validity, fit): fit only breaks ties among words of equal validity
    ranked = sorted(uniq, key=lambda c: (_validity(c, lang), _fit(c, context, lang)), reverse=True)
    best = ranked[0]
    runner_validity = _validity(ranked[1], lang) if len(ranked) > 1 else 0.0
    confidence = _validity(best, lang) - runner_validity     # 1.0 only: real word vs non-word
    return best, round(confidence, 4)
