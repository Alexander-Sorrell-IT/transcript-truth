"""Speaker consensus across independent diarizers.

Single-diarizer speaker labels are unreliable on overlapping crosstalk (the diarizer
guesses). Pooling several independent diarizers — Deepgram (acoustic), ElevenLabs Scribe
(acoustic, different family), and a name-tagged video read (visual) — lets us (a) agree on
WHERE the speaker changes and (b) carry a stable role/name per voice. Where the sources
agree, confidence is high; where they split, the turn is flagged for a human ear.

Each source is a list of turns: [{start, end, speaker, text}]. speaker ids are whatever
that source emits (Deepgram int, Scribe 'speaker_0', video 'ROBERT'); they are NOT assumed
comparable across sources — we compare CHANGE STRUCTURE and map ids by time-overlap voting.
"""
from collections import defaultdict


def speaker_at(turns, t):
    """The speaker id a source assigns at time t (or None if t is outside its turns)."""
    for u in turns:
        if u["start"] <= t <= u.get("end", u["start"]) + 0.01:
            return u["speaker"]
    # fall back to the nearest preceding turn
    prev = [u for u in turns if u["start"] <= t]
    return prev[-1]["speaker"] if prev else None


def apply_reference_speakers(turns, reference):
    """Reference-map: relabel each turn's speaker by a whole-file reference diarization, looked
    up at the turn's midpoint. Lets chunked text-witness turns (which can't keep speaker ids
    consistent across chunks) inherit globally-consistent speakers from ONE whole-file pass.
    Measured 95.8% diarization-agreement vs ground truth — beats chunk-only reconciliation (~90%)
    because identity never depends on a speaker happening to talk at a chunk seam."""
    out = []
    for t in turns:
        mid = (t["start"] + t.get("end", t["start"])) / 2
        spk = speaker_at(reference, mid)
        out.append({**t, "speaker": spk if spk is not None else t.get("speaker")})
    return out


def map_ids(ref, other, t0, t1, step=0.5):
    """Build a map other_id -> ref_id by majority time-overlap voting across [t0,t1].
    Lets us translate one diarizer's labels into another's frame so they can be compared."""
    votes = defaultdict(lambda: defaultdict(float))
    t = t0
    while t <= t1:
        a, b = speaker_at(ref, t), speaker_at(other, t)
        if a is not None and b is not None:
            votes[b][a] += step
        t += step
    return {b: max(cand, key=cand.get) for b, cand in votes.items()}


def consensus_turns(sources, t0, t1, step=0.5):
    """sources: dict name->turns. Returns a per-turn consensus over [t0,t1] using the FIRST
    source as the timing reference. Each reference turn gets: the ref speaker, every other
    source's speaker (mapped into the ref's id space), and whether they AGREE (= confidence).
    """
    names = list(sources)
    ref_name = names[0]
    ref = sources[ref_name]
    maps = {n: map_ids(ref, sources[n], t0, t1, step) for n in names[1:]}
    out = []
    for u in ref:
        if u["end"] < t0 or u["start"] > t1:
            continue
        mid = (u["start"] + u["end"]) / 2
        row = {"start": u["start"], "end": u["end"], "text": u["text"],
               ref_name: u["speaker"]}
        labels = [u["speaker"]]
        for n in names[1:]:
            raw = speaker_at(sources[n], mid)
            mapped = maps[n].get(raw, raw)
            row[n] = mapped
            labels.append(mapped)
        # agreement = all non-None labels identical
        nn = [x for x in labels if x is not None]
        row["agree"] = len(set(nn)) <= 1 and len(nn) == len(names)
        out.append(row)
    return out


def cross_consensus(sources, t0, t1, step=0.5):
    """Cross-diarizer consensus across {name: turns} (≥2 independent diarizers).

    Uses the FIRST source as the timing/text reference (pass the most reliable diarizer
    first — e.g. an acoustic one like Deepgram). Per turn: where every diarizer maps to the
    same speaker -> high confidence; where they SPLIT -> the turn is flagged for review (the
    engine's philosophy: surface disagreement, never hide it behind one model). Returns:
      turns          : reference turns each with per-diarizer speaker + `agree` flag
      agreement_pct  : % of turns all diarizers agree on (None if <2 diarizers)
      n_diarizers    : how many actually contributed
      speaker_counts : {name: distinct speaker count} — exposes count disagreements (e.g.
                       2 acoustic models say 3, an LLM says 6)
      review_turns   : the flagged (disagreement) turns, the short list to ear-check
    """
    names = list(sources)
    counts = {n: len({x["speaker"] for x in sources[n]}) for n in names}
    if len(names) < 2:
        only = sources[names[0]] if names else []
        return {"turns": [{**t, "agree": None} for t in only], "agreement_pct": None,
                "n_diarizers": len(names), "speaker_counts": counts, "review_turns": []}
    rows = consensus_turns(sources, t0, t1, step)
    agree = sum(1 for r in rows if r.get("agree"))
    review = [r for r in rows if not r.get("agree")]
    return {"turns": rows, "agreement_pct": round(100 * agree / max(len(rows), 1), 1),
            "n_diarizers": len(names), "speaker_counts": counts, "review_turns": review}
