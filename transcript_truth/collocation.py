"""The no-AI 'does this word make sense here?' layer.

For each content word in a transcript, look at the other content words in the same
sentence. If the word is real but NONE of its neighbours are among the words it
normally co-occurs with (from the Wikipedia collocation table), it doesn't fit its
context -- the signal that a homophone/mishearing slipped in (群島 fits 湖/諸島;
軍島 fits nothing). Pure table lookup, no model.
"""
import json, os, functools
from sudachipy import dictionary, tokenizer

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tok = dictionary.Dictionary().create()
_MODE = tokenizer.Tokenizer.SplitMode.C
_CONTENT = {"名詞", "動詞", "形容詞"}


@functools.lru_cache(maxsize=1)
def colloc():
    f = os.path.join(_DIR, "data", "jp_collocations.json")
    try:
        return json.load(open(f, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _content(text):
    out = []
    for m in _tok.tokenize(text, _MODE):
        if m.part_of_speech()[0] in _CONTENT and len(m.surface()) > 1:
            out.append(m.surface())
    return out


def coherence_report(text):
    """Returns list of {word, fits, neighbors_matched, expected} for content words
    that HAVE collocation data, so a caller can see which words fit their context
    and which don't. A word with collocation data but zero neighbour matches is the
    'does not make sense here' signal."""
    words = _content(text)
    table = colloc()
    report = []
    for i, w in enumerate(words):
        if w not in table:
            continue  # no data to judge by (rare word / proper noun) -> stay silent
        neighbors = [x for j, x in enumerate(words) if j != i]
        expected = set(table[w])
        matched = [n for n in neighbors if n in expected]
        report.append({
            "word": w,
            "fits": bool(matched),
            "neighbors_matched": matched,
            "expected_sample": table[w][:6],
        })
    return report


def misfit_words(text):
    """The flags: real words (have collocation data) whose sentence neighbours are
    NONE of their usual companions -> likely the wrong word for this context."""
    return [r for r in coherence_report(text) if not r["fits"]]


def _kata2hira(s):
    """Sudachi readings are katakana; the homophone index is keyed in hiragana."""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


@functools.lru_cache(maxsize=1)
def _homophones():
    f = os.path.join(_DIR, "data", "jp_homophones_by_reading.json")
    try:
        return json.load(open(f, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def suggest_corrections(text):
    """The real 'does it make sense' check on ONE transcript: for each content word
    that has same-reading homophones (記者/汽車), score every candidate by collocation
    fit with the rest of the sentence. If a DIFFERENT candidate fits strictly better
    than the written word, flag it as a likely mishearing. Conservative on purpose:
    silent unless an alternative genuinely fits better. No model."""
    table, H = colloc(), _homophones()
    morphs = [m for m in _tok.tokenize(text, _MODE)]
    content = [(i, m.surface(), m.reading_form()) for i, m in enumerate(morphs)
               if m.part_of_speech()[0] in _CONTENT and len(m.surface()) > 1]
    surfaces = [s for _, s, _ in content]
    flags = []
    for k, (_, surf, read) in enumerate(content):
        cands = [c["word"] for c in H.get(_kata2hira(read), [])]
        if surf not in cands or len(cands) < 2:
            continue  # only judge genuine same-reading ambiguities the written word is part of
        neighbors = [s for j, s in enumerate(surfaces) if j != k]
        def fit(w):
            return sum(1 for n in neighbors if n in set(table.get(w, [])))
        scored = sorted(((fit(c), c) for c in cands), reverse=True)
        best_score, best = scored[0]
        written_score = fit(surf)
        # require a STRONG fit for the alternative (>=2 matching companions) and a clear
        # margin over the written word — cuts weak-signal false positives.
        if best != surf and best_score >= 2 and best_score - written_score >= 2:
            flags.append({"written": surf, "reading": read, "suggest": best,
                          "written_fit": written_score, "suggest_fit": best_score})
    return flags
