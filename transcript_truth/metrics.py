"""Measurement (Phase 1 foundation) — turn 'better' into a number.

diar_agreement: compare two diarizations on the SAME audio and report what fraction of the
timeline they assign to the same speaker. Speaker ids aren't comparable across systems
(one says 'speaker_0', the other 'A'), so we first map the hypothesis ids onto the reference
ids by majority time-overlap (the same voting `speaker_consensus.map_ids` uses), then score.

This is what lets us test chunked diarization against a trusted whole-file reference: if the
chunked result matches the whole-file result on ~95%+ of the timeline with the same speaker
count, the chunking preserved identity. A broken chunker (phantom speakers) scores low.
"""
from __future__ import annotations
from .speaker_consensus import speaker_at, map_ids


def _span(turns):
    lo = min((t["start"] for t in turns), default=0.0)
    hi = max((t["end"] for t in turns), default=0.0)
    return lo, hi


def diar_agreement(ref, hyp, step=0.5, dur=None):
    """ref, hyp: lists of {start, end, speaker}. Returns a dict:
      agreement_pct : % of sampled timeline where hyp's mapped speaker == ref's speaker
      ref_speakers  : distinct speaker count in ref
      hyp_speakers  : distinct speaker count in hyp
      mapped_speakers : distinct hyp speakers that mapped onto a ref speaker
      idmap         : hyp_id -> ref_id mapping used
    Both speech-only (silence where neither has a turn is skipped)."""
    if not ref or not hyp:
        return {"agreement_pct": 0, "ref_speakers": len({t["speaker"] for t in ref}),
                "hyp_speakers": len({t["speaker"] for t in hyp}), "mapped_speakers": 0, "idmap": {}}
    lo = min(_span(ref)[0], _span(hyp)[0])
    hi = dur if dur is not None else max(_span(ref)[1], _span(hyp)[1])
    idmap = map_ids(ref, hyp, lo, hi, step)        # hyp id -> ref id by overlap voting

    same = total = 0
    t = lo
    while t <= hi:
        r = speaker_at(ref, t)
        h = speaker_at(hyp, t)
        if r is not None and h is not None:        # both have speech here
            total += 1
            if idmap.get(h, h) == r:
                same += 1
        t += step
    return {
        "agreement_pct": round(100 * same / total, 1) if total else 0,
        "ref_speakers": len({x["speaker"] for x in ref}),
        "hyp_speakers": len({x["speaker"] for x in hyp}),
        "mapped_speakers": len(set(idmap.values())),
        "idmap": idmap,
    }


_UNITS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,
          "nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,
          "sixteen":16,"seventeen":17,"eighteen":18,"nineteen":19,"twenty":20,"thirty":30,
          "forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90,
          "first":1,"second":2,"third":3,"fifth":5,"eighth":8,"ninth":9,"twelfth":12}
_SCALES = {"hundred":100,"thousand":1000,"million":1000000,"billion":1000000000}
_ORD = lambda w: w[:-2] if w[-2:] in ("th","st","nd","rd") and w[:-2].isdigit() else w


_ORD_WORD = {"first": "one", "second": "two", "third": "three", "fourth": "four", "fifth": "five",
             "sixth": "six", "seventh": "seven", "eighth": "eight", "ninth": "nine", "tenth": "ten",
             "eleventh": "eleven", "twelfth": "twelve", "thirteenth": "thirteen", "twentieth": "twenty",
             "thirtieth": "thirty"}
_NUMWORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
             "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
             "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
             "hundred", "thousand", "million", "billion", "trillion"}


def _normalize_numbers(text):
    """Canonicalize number/currency FORMATTING so WER measures words, not style: spelled cardinals
    -> digits (via word2number), %/$ normalized, commas + ordinal suffixes stripped. CONSERVATIVE by
    design — it never invents a wrong number: hyphenated DIGIT ranges (5-10) and phone numbers are
    left intact (not summed), years-spelled-as-words are left alone (no fragile year guess), and any
    word-run word2number can't parse is left verbatim. Under-normalizes rare cases rather than mangle
    common ones (the twenty-one->2001 / 5-10->15 class of bug)."""
    import re
    s = text.lower()
    s = s.replace("%", " percent ").replace("$", " ")
    s = re.sub(r"(\d),(\d)", r"\1\2", s)                       # 47,000,000 -> 47000000
    s = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", s)            # 3rd -> 3
    s = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", s)                # WORD-word hyphen -> space (compounds only)
    toks = s.split()
    out, i = [], 0
    while i < len(toks):
        core = _ORD_WORD.get(toks[i].strip(".,;:!?'"), toks[i].strip(".,;:!?'"))
        if core in _NUMWORDS:
            run, j = [], i
            while j < len(toks):
                c = _ORD_WORD.get(toks[j].strip(".,;:!?'"), toks[j].strip(".,;:!?'"))
                if c in _NUMWORDS or c == "and":
                    run.append(c); j += 1
                else:
                    break
            while run and run[-1] == "and":
                run.pop(); j -= 1
            try:
                from word2number import w2n
                out.append(str(w2n.word_to_num(" ".join(run))))
            except Exception:
                out.extend(toks[i:j])                          # not a clean cardinal -> leave verbatim
            i = j
            continue
        out.append(toks[i]); i += 1
    # collapse "<digit> <scale>" so "47 million" (=47 1000000) matches "forty seven million" (=47000000)
    _SCALE_INT = {"100", "1000", "1000000", "1000000000", "1000000000000"}
    merged = []
    for t in out:
        if merged and t in _SCALE_INT and re.fullmatch(r"\d+(\.\d+)?", merged[-1] or ""):
            v = float(merged[-1]) * int(t)
            merged[-1] = str(int(v)) if v == int(v) else str(v)
        else:
            merged.append(t)
    return " ".join(merged)


def wer(reference: str, hypothesis: str, normalize_numbers: bool = True):
    """Word Error Rate (Levenshtein over words) — the text-accuracy ruler. 0.0 = identical.
    Case/punctuation-insensitive. With normalize_numbers (default) it canonicalizes number/
    date/currency formatting so "15%" and "fifteen percent" don't count as an error — measuring
    real word accuracy, not style. Pass normalize_numbers=False for raw formatting-sensitive WER."""
    import re
    if normalize_numbers:
        reference, hypothesis = _normalize_numbers(reference), _normalize_numbers(hypothesis)

    def _tokenize(s):
        # Space-free scripts (CJK: Han, Hiragana, Katakana, Hangul) have no word boundaries, so
        # splitting on spaces yields ~1 "word" and WER becomes meaningless. Tokenize those by
        # CHARACTER (the standard CER for CJK) while keeping run-length Latin/Cyrillic words intact.
        s = re.sub(r"[^\w\s']", " ", s.lower())
        toks = []
        for m in re.finditer(r"[぀-ヿ㐀-䶿一-鿿가-힣]|[^\s]+", s):
            g = m.group(0)
            if re.fullmatch(r"[぀-ヿ㐀-䶿一-鿿가-힣]", g):
                toks.append(g)                     # one CJK char = one token
            else:
                toks.extend(g.split())
        return toks

    r, h = _tokenize(reference), _tokenize(hypothesis)
    if not r:
        return 0.0 if not h else 1.0
    # DP edit distance
    prev = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        cur = [i] + [0] * len(h)
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return round(prev[len(h)] / len(r), 4)
