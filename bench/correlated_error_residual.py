"""Empirical test of the system's known weak spot: when a transcript error MATCHES
Whisper's own mishearing, comparing transcript-vs-Whisper (the audio anchor) cannot
catch it. So we measure the *true residual*: errors Whisper ITSELF makes (whisper != gold),
which the audio anchor is blind to by construction, and ask whether the OTHER witnesses
catch them:
    (a) Qwen worker correct_transcript(whisper_text) -- a text-only second witness
    (b) deterministic auditor audit_transcript(whisper_text)

Method (per advisor):
  - normalize: strip whitespace + JP/ASCII punctuation from gold & whisper & qwen.
  - align gold<->whisper and gold<->qwen INDEPENDENTLY with difflib (char-level; no
    tokenizer dep). Qwen rewrites freely (kana-normalization etc.) so we cannot track a
    whisper->qwen span; we re-anchor each on gold.
  - A Whisper error = a non-'equal' opcode span in gold<->whisper (the gold piece is
    mis-rendered). caught_by_qwen = that same gold span comes back 'equal' in gold<->qwen.
  - caught_by_auditor = audit_transcript(whisper_text) emits a flag whose evidence overlaps
    the whisper error text (substring). Only context_homophone can plausibly fire.
  - missed_by_all = error and not qwen and not auditor  ==  TRUE RESIDUAL.

Whisper is cached to JSON so reruns never re-transcribe.
"""
from __future__ import annotations
import os, sys, json, glob, re, difflib, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SOUNDS = os.path.join(ROOT, "data", "sounds")
CACHE = os.path.join(ROOT, "bench", "_whisper_medium_cache.json")
OUT = os.path.join(ROOT, "bench", "correlated_error_residual_result.json")
N_CAP = 20

# punctuation + whitespace to strip before alignment (so formatting diffs don't count as mishearings)
_STRIP = re.compile(r"[\s　、。，．・「」『』（）()\[\]【】〔〕？！?!:：;；\-ー…—–\"'`~]+")


def norm(s: str) -> str:
    return _STRIP.sub("", s.strip())


def load_cache():
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    return {}


def save_cache(c):
    json.dump(c, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def transcribe_all(clips):
    cache = load_cache()
    todo = [c for c in clips if os.path.basename(c) not in cache]
    if todo:
        from faster_whisper import WhisperModel
        m = WhisperModel("medium", device="cpu", compute_type="int8")
        for c in todo:
            name = os.path.basename(c)
            t = time.time()
            segs, _ = m.transcribe(c, language="ja")
            txt = "".join(s.text for s in segs)
            cache[name] = txt
            save_cache(cache)  # persist after every clip
            print(f"  whisper {name}: {round(time.time()-t,1)}s -> {txt[:40]}", flush=True)
    return cache


def error_spans(gold_n: str, hyp_n: str):
    """Return list of (gold_substring, hyp_substring, tag) for every non-equal opcode
    in the gold<->hyp char alignment. gold_substring is the gold piece that was mis-rendered."""
    sm = difflib.SequenceMatcher(None, gold_n, hyp_n, autojunk=False)
    spans = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        spans.append({"tag": tag, "gold": gold_n[i1:i2], "hyp": hyp_n[j1:j2],
                      "g_i1": i1, "g_i2": i2})
    return spans


def gold_equal_ranges(gold_n: str, hyp_n: str):
    """Set of gold char indices that are in an 'equal' block of the gold<->hyp alignment."""
    sm = difflib.SequenceMatcher(None, gold_n, hyp_n, autojunk=False)
    ok = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            ok.update(range(i1, i2))
    return ok


def main():
    from transcript_truth.worker import correct_transcript
    from transcript_truth.engine import audit_transcript

    clips = sorted(glob.glob(os.path.join(SOUNDS, "clip_*.wav")))[:N_CAP]
    print(f"Clips: {len(clips)} (cap {N_CAP})", flush=True)

    wcache = transcribe_all(clips)

    rows = []
    misses = []
    n_err = n_q = n_a = n_miss = 0

    for c in clips:
        name = os.path.basename(c)
        gold_raw = open(c.replace(".wav", ".txt"), encoding="utf-8").read().strip()
        whisper_raw = wcache[name]
        gold_n = norm(gold_raw)
        whisper_n = norm(whisper_raw)

        # the audio anchor compares transcript-under-test against whisper; where whisper
        # itself != gold, that error is INVISIBLE to the anchor. Enumerate those spans.
        spans = error_spans(gold_n, whisper_n)

        # witness (a): Qwen corrects whisper's text (text-only second witness)
        qwen_raw = correct_transcript(whisper_raw)
        qwen_n = norm(qwen_raw)
        gold_ok_after_qwen = gold_equal_ranges(gold_n, qwen_n)

        # witness (b): deterministic auditor on whisper's text
        receipt = audit_transcript(whisper_raw)
        flag_ev = [f.evidence for f in receipt.flags]
        flag_lbls = [(f.rule, f.evidence, f.label) for f in receipt.flags]

        for sp in spans:
            n_err += 1
            gold_piece = sp["gold"]
            hyp_piece = sp["hyp"]
            # caught_by_qwen: the gold chars under this error are ALL 'equal' in gold<->qwen
            rng = range(sp["g_i1"], sp["g_i2"])
            if len(gold_piece) == 0:
                # pure insertion by whisper (extra chars, no gold span). Did qwen drop it?
                # treat as caught if those hyp chars don't survive into qwen (can't track cleanly);
                # conservatively: caught_by_qwen iff hyp_piece not substring of qwen_n
                caught_q = hyp_piece not in qwen_n
            else:
                caught_q = all(i in gold_ok_after_qwen for i in rng)
            # caught_by_auditor: any flag evidence overlaps the misheard hyp text
            caught_a = False
            hit_flag = None
            for rule, ev, lbl in flag_lbls:
                evn = norm(ev)
                if hyp_piece and evn and (evn in hyp_piece or hyp_piece in evn):
                    caught_a, hit_flag = True, (rule, ev)
                    break
            if caught_q:
                n_q += 1
            if caught_a:
                n_a += 1
            row = {"clip": name, "tag": sp["tag"], "gold": gold_piece, "whisper": hyp_piece,
                   "caught_qwen": caught_q, "caught_auditor": caught_a,
                   "auditor_flag": hit_flag}
            rows.append(row)
            if not caught_q and not caught_a:
                n_miss += 1
                misses.append(row)

    summary = {
        "n_clips": len(clips),
        "n_whisper_error_spans": n_err,
        "caught_by_qwen": n_q,
        "caught_by_auditor": n_a,
        "missed_by_all_TRUE_RESIDUAL": n_miss,
        "missed_examples": misses,
    }
    json.dump({"summary": summary, "rows": rows,
               "whisper_cache_keys": list(wcache.keys())},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n===== RESULT =====", flush=True)
    print(f"clips                         : {len(clips)}")
    print(f"Whisper error spans (vs gold) : {n_err}   <- audio anchor is BLIND to all of these")
    print(f"  caught by Qwen correction   : {n_q}")
    print(f"  caught by deterministic aud : {n_a}")
    print(f"  MISSED BY ALL (true residual): {n_miss}")
    print(f"\nwrote {OUT}")
    print("\n-- sample of missed (correlated) errors --")
    for m in misses[:25]:
        print(f"  [{m['clip']}] {m['tag']:7s} gold={m['gold']!r}  whisper={m['whisper']!r}")


if __name__ == "__main__":
    main()
