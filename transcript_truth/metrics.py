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


def _normalize_numbers(text):
    """Canonicalize number/date/currency FORMATTING so WER measures words, not style:
    spelled numbers -> digits, %/$ -> words, strip commas + ordinal suffixes, two adjacent
    2-digit words read as a year (twenty twenty-five -> 2025). Bounded — covers the common
    transcription cases, not every exotic numeral."""
    import re
    s = text.lower().replace("-", " ")
    s = s.replace("%", " percent ").replace("$", " dollars ")
    s = re.sub(r"(\d),(\d)", r"\1\2", s)                 # 47,000,000 -> 47000000
    s = re.sub(r"[,.;:]", " | ", s)                       # keep punctuation as run-breakers
    toks = [_ORD(t) for t in re.sub(r"[^\w\s'|]", " ", s).split()]
    out, i = [], 0
    while i < len(toks):
        cur, used, scaled = 0, False, 0
        j = i
        while j < len(toks):                             # collect a run of numbers (words OR digits)
            w = toks[j]
            if w in _UNITS:
                cur += _UNITS[w]; used = True; j += 1
            elif w.isdigit():
                cur += int(w); used = True; j += 1
            elif w in _SCALES:
                cur = (cur or 1) * _SCALES[w]; scaled += cur; cur = 0; used = True; j += 1
            elif w == "and" and used:
                j += 1
            else:
                break                                    # punctuation '|' or any non-number breaks the run
        if used:
            val = scaled + cur
            # year: "twenty twenty five" / "nineteen ninety nine" -> 2025 / 1999
            if scaled == 0 and toks[i] in ("twenty", "nineteen") and j - i >= 2:
                a = _UNITS.get(toks[i], 0); b = sum(_UNITS.get(t, 0) for t in toks[i+1:j])
                if 0 < b < 100:
                    val = a * 100 + b
            out.append(str(val)); i = j
        else:
            if toks[i] != "|":
                out.append(toks[i])
            i += 1
    return " ".join(out)


def wer(reference: str, hypothesis: str, normalize_numbers: bool = True):
    """Word Error Rate (Levenshtein over words) — the text-accuracy ruler. 0.0 = identical.
    Case/punctuation-insensitive. With normalize_numbers (default) it canonicalizes number/
    date/currency formatting so "15%" and "fifteen percent" don't count as an error — measuring
    real word accuracy, not style. Pass normalize_numbers=False for raw formatting-sensitive WER."""
    import re
    if normalize_numbers:
        reference, hypothesis = _normalize_numbers(reference), _normalize_numbers(hypothesis)
    norm = lambda s: re.sub(r"[^\w\s']", " ", s.lower()).split()
    r, h = norm(reference), norm(hypothesis)
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
