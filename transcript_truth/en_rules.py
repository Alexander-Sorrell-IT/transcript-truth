"""English homophone / confusable-word verification — the English parallel to the
Japanese coherence witness. Qwen proofreads ONLY for homophone errors; a flag is
accepted ONLY if both the written and the suggested word live in the same confusable
set (data/en_homophones.json), so Qwen can't push through a non-homophone rewrite.
"""
import os, json, re, functools
from .types import Flag
from .worker import qwen

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _norm(w):
    """Apostrophe/comma-insensitive: they're -> theyre, it's -> its (matches the catalog)."""
    return w.lower().replace("'", "").replace("’", "").replace(",", "").strip(".!?\" ")


@functools.lru_cache(maxsize=1)
def _index():
    try:
        sets = json.load(open(os.path.join(_DIR, "data", "en_homophones.json")))["sets"]
    except FileNotFoundError:
        return {}
    idx = {}
    for s in sets:
        norm = set(_norm(x) for x in s)
        for w in s:
            idx[_norm(w)] = norm
    return idx


def _same_set(a, b):
    idx = _index()
    a, b = _norm(a), _norm(b)
    return a in idx and b in idx[a]


def en_homophone_errors(text):
    """Return Flags for English homophone errors in `text`, each gated by the catalog."""
    if not re.search(r"[A-Za-z]", text):
        return []
    prompt = (
        "Proofread the English in the text below ONLY for homophone / commonly-confused-word "
        "errors (there/their/they're, to/too/two, your/you're, its/it's, then/than, "
        "affect/effect, lose/loose, etc.). List ONLY actual errors, one per line, as "
        "`wrong -> right`. Change nothing else. If there are none, reply exactly `none`.\n\n"
        f"Text:\n{text}"
    )
    try:
        out = qwen([{"role": "user", "content": prompt}], max_tokens=300)
    except Exception:
        return []
    flags = []
    for line in out.splitlines():
        if "->" not in line:
            continue
        a, b = line.split("->", 1)
        a, b = a.strip(" `-*0123456789.").strip(), b.strip(" `*").strip()
        a, b = a.strip("\"'.,"), b.strip("\"'.,")
        if a and b and a.lower() != b.lower() and _same_set(a, b) and re.search(rf"\b{re.escape(a)}\b", text, re.I):
            flags.append(Flag(
                rule="en_homophone", severity="review",
                label=f"'{a}' may be the wrong word here — should it be '{b}'? (homophone)",
                evidence=a, fix=f"Check: '{a}' vs '{b}' — pick the one that fits the sentence."))
    return flags
