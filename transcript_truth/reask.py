"""Contested-span re-ask loop (PERFECTION_PLAN Phase III.1) — task-routed model use.

The consensus already KNOWS where its errors live: the uncertain_spans it surfaces. This stage
spends targeted attention exactly there — cut just those seconds of audio, re-send the slice to
(a) the measured-strongest witness for the language and (b) context-primed Gemini (candidates +
neighbor words), then let a DETERMINISTIC adoption rule decide:

    adopt only if BOTH fresh readers propose the same word for the slot (script-folded match)
    AND that word is plausible (a dictionary word, a gazetteer name, or one of the original
    witnesses' variants — a re-ask can promote an existing minority read, never invent freely).

Models propose (now with focused attention); code still owns the verdict. Spans that don't meet
the rule stay flagged for human review — honest uncertainty is preserved, never papered over.
"""
from __future__ import annotations
import difflib
import os
import subprocess
import tempfile

_PAD_S = 1.5          # seconds of context on each side of the estimated span
_MIN_SLICE_S = 2.0    # never cut a slice shorter than this (witnesses need runway)
_MAX_SPANS = 6        # cost cap per file: re-ask the first N contested spans only


def _cut(audio_path: str, t0: float, t1: float) -> str:
    """ffmpeg-cut [t0, t1] to a temp wav (16k mono). Caller removes it."""
    fd, out = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ss", f"{t0:.2f}", "-to", f"{t1:.2f}",
                    "-ac", "1", "-ar", "16000", out, "-loglevel", "error"], check=True)
    return out


def _slot_word(fresh_text: str, toks: list[str], i: int) -> str | None:
    """Which word does a fresh read propose for output position i? Align the fresh read's tokens
    against the neighborhood of i and return the token that maps onto i (None if the alignment
    doesn't cover the position 1:1 — no guess)."""
    ftoks = fresh_text.split()
    if not ftoks:
        return None
    lo, hi = max(0, i - 3), min(len(toks), i + 4)
    window = [t.lower() for t in toks[lo:hi]]
    sm = difflib.SequenceMatcher(a=window, b=[t.lower() for t in ftoks], autojunk=False)
    want = i - lo
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if i1 <= want < i2:
            if op == "equal":
                return ftoks[j1 + (want - i1)]
            if op == "replace" and (i2 - i1) == (j2 - j1):
                return ftoks[j1 + (want - i1)]
            return None
    return None


def _variants_at(reads: dict, toks: list[str], i: int) -> set[str]:
    """Every original witness's word at output position i (by re-alignment)."""
    out = {toks[i]}
    low = [t.lower() for t in toks]
    for txt in reads.values():
        if not txt:
            continue
        ot = txt.split()
        sm = difflib.SequenceMatcher(a=low, b=[t.lower() for t in ot], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "replace" and i1 <= i < i2 and (i2 - i1) == (j2 - j1):
                out.add(ot[j1 + (i - i1)])
    return out


def _known(word: str, lang: str | None) -> bool:
    """Dictionary word or gazetteer name — the plausibility rank used by the adoption guards."""
    from .adjudicate import _is_word, _name_in_gazetteer
    w = word.strip(".,;:!?'’،؛؟")
    return _is_word(w, lang) or _name_in_gazetteer(w.lower()) or _name_in_gazetteer(w)


def _plausible(word: str, variants: set[str], lang: str | None) -> bool:
    """A re-ask proposal must be a known word, a known name, or an existing witness variant —
    the re-ask can promote a minority read or a known form, never free-invent."""
    from .adjudicate import _is_word, _name_in_gazetteer
    w = word.strip(".,;:!?'’،؛؟")
    if w.lower() in {v.lower().strip(".,;:!?'’،؛؟") for v in variants}:
        return True
    return _is_word(w, lang) or _name_in_gazetteer(w.lower()) or _name_in_gazetteer(w)


def reask_contested(audio_path: str, reads: dict, lang: str | None, result: dict,
                    max_spans: int = _MAX_SPANS) -> dict:
    """Re-ask loop over a consensus_tokens result. Returns the (possibly updated) result;
    resolved spans get by='reask', unresolved spans stay contested. Graceful: any witness
    failure on a slice just means that span stays flagged."""
    from . import chunking, consensus as C
    from .metrics import _fold_script

    spans = [s for s in result.get("uncertain_spans", []) if "word" in s]
    if not spans or not chunking.have_ffmpeg():
        return result
    toks = result["text"].split()
    dur = chunking.probe(audio_path)[0]
    if not dur:
        return result

    # TWO fresh readers, always (a lone fresh opinion adopted correlated garbles in measurement):
    # the measured-strongest non-gemini witness does the acoustic re-listen; context-primed gemini
    # is the second ear, with the next different-family roster witness (or local whisper) as the
    # fallback when gemini is rate-limited.
    ranked = sorted(C.ROSTER.get(lang, C.ROSTER.get("en", [])),
                    key=lambda n: -C._reliability(n, lang))
    best = next((n for n in ranked if n != "gemini"), None)
    # second-ear chain: any different-family witness can confirm; walked in reliability order
    # until one actually yields a slot word (a re-listener that can't align the slot abstains,
    # it doesn't veto)
    chain = [n for n in ranked if n != "gemini" and best and C._family(n) != C._family(best)]
    if "whisper" not in chain and best != "whisper" and C._family(best or "") != "whisper":
        chain.append("whisper")

    for s in spans[:max_spans]:
        i = s["index"]
        if i >= len(toks):
            continue
        t0 = max(0.0, dur * i / max(1, len(toks)) - _PAD_S)
        t1 = min(dur, dur * (i + 1) / max(1, len(toks)) + _PAD_S)
        if t1 - t0 < _MIN_SLICE_S:
            mid = (t0 + t1) / 2
            t0, t1 = max(0.0, mid - _MIN_SLICE_S / 2), min(dur, mid + _MIN_SLICE_S / 2)
        variants = _variants_at(reads, toks, i)
        ctx = (f"Candidate words heard by other systems for one unclear word: "
               f"{', '.join(sorted(variants))}. Surrounding words: "
               f"\"{' '.join(toks[max(0, i - 2):i])} ___ {' '.join(toks[i + 1:i + 3])}\".")
        clip = None
        try:
            clip = _cut(audio_path, t0, t1)
            proposals = []                        # (word, source) — sources must be independent
            if best:
                try:
                    w = _slot_word(C._witness_call(best, clip, lang) or "", toks, i)
                    if w:
                        proposals.append((w, best))
                except Exception:
                    pass
            try:
                from .witness import gemini_read
                w = _slot_word(gemini_read(clip, language=lang, context=ctx) or "", toks, i)
                if w:
                    proposals.append((w, "gemini"))
            except Exception:                     # rate-limit/quota — walk the fallback chain
                pass
            for fb in chain:
                if len(proposals) >= 2:
                    break
                try:
                    w = _slot_word(C._witness_call(fb, clip, lang) or "", toks, i)
                    if w:
                        proposals.append((w, fb))
                except Exception:
                    pass

            def fold(x):
                return _fold_script(x.lower().strip(".,;:!?'’،؛؟"), lang)

            # adoption rule: TWO fresh independent ears agree on the slot word (a lone fresh
            # opinion measured as adopting correlated garbles), it differs from the incumbent,
            # it's plausible, and it never DOWNGRADES a known word/name to an unknown string
            # (measured: that guard is what blocks 'Yamamoto'→'Yamanoto').
            words = {fold(w) for w, _ in proposals}
            if len(proposals) >= 2 and len(words) == 1:
                w0 = proposals[0][0]
                # length guard: a fresh ear must not replace a long token with a fragment of it
                # (measured: two ears agreed on 'أو' ("or") for the name garble 'أوكوموكو')
                if len(fold(w0)) < max(3, len(fold(toks[i])) // 2):
                    continue
                if fold(w0) != fold(toks[i]) and _plausible(w0, variants, lang) \
                        and not (_known(toks[i], lang) and not _known(w0, lang)):
                    s.pop("word", None)
                    s.pop("contested", None)
                    s.update({"from": toks[i], "to": w0, "by": "reask"})
                    toks[i] = w0
        finally:
            if clip and os.path.exists(clip):
                os.remove(clip)

    result["text"] = " ".join(toks)
    return result
