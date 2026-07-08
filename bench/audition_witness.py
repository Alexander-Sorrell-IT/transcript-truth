#!/usr/bin/env python3
"""Witness audition harness (PERFECTION_PLAN III.3) — one command, measured verdict.

    python3 bench/audition_witness.py <model> <lang> [--commit]

<model> is either a built-in witness name (deepgram, scribe, gemini, whisper, mms, seamless,
phowhisper, wav2vec2) or a HuggingFace ASR model id (org/name — run locally via transformers).
Runs every fp_<lang>* battery clip, prints per-clip WER + the roster comparison, and a verdict:

    ROSTER-WORTHY  — beats the language's current weakest roster witness
    VOTE-FODDER    — worse than the roster but decorrelated enough to consider as a extra family
    REJECT         — measured worse with no redeeming signal

--commit writes the reliability row into data/witness_reliability.json (HF ids get a slug name).
Nothing registers without a measurement — this is the mechanism that keeps the roster honest.
(Turkish specialists 2026-07-07: 300M XLSR = 0.623, whisper-turbo-finetune = 0.380 — both would
have been REJECT here in ten minutes instead of a session.)
"""
import os, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for line in open(os.path.join(ROOT, ".env")):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1); os.environ[k.strip()] = v.strip()
sys.path.insert(0, ROOT)
from transcript_truth import consensus as C, metrics as M

BUILTIN = {"deepgram", "scribe", "gemini", "whisper", "mms", "seamless", "phowhisper", "wav2vec2"}


def make_reader(model: str, lang: str):
    if model in BUILTIN:
        return lambda wav: C._witness_call(model, wav, lang)
    from transformers import pipeline
    import torch
    pipe = pipeline("automatic-speech-recognition", model=model, dtype=torch.float32, device="cpu")
    return lambda wav: pipe(wav)["text"].strip()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    commit = "--commit" in sys.argv
    if len(args) != 2:
        sys.exit(__doc__)
    model, lang = args
    slug = model if model in BUILTIN else model.split("/")[-1][:24].replace("-", "_")

    clips = sorted(glob.glob(os.path.join(ROOT, "bench", "battery", f"fp_{lang}*.json")))
    if not clips:
        sys.exit(f"no battery for '{lang}' — generate fp_{lang}* clips first (the mechanism "
                 f"REQUIRES a measurement; see make_multilang_battery.py)")
    read = make_reader(model, lang)

    wers = []
    for jp in clips:
        meta = json.load(open(jp, encoding="utf-8"))
        try:
            text = read(jp[:-5] + ".wav") or ""
        except Exception as e:
            print(f"  {os.path.basename(jp):14} witness error: {e}")
            text = ""
        w = M.wer(meta["text"], text, lang=lang) if text else 1.0
        wers.append(w)
        print(f"  {os.path.basename(jp):14} wer={w:.3f}  {text[:80]}", flush=True)
    avg = sum(wers) / len(wers)

    rel_path = os.path.join(ROOT, "data", "witness_reliability.json")
    table = json.load(open(rel_path, encoding="utf-8"))
    roster = table.get(lang, {})
    weakest = min(roster.values()) if roster else 0.0
    score = round(max(0.0, 1.0 - avg), 3)

    print(f"\n{model} @ {lang}: avg WER {avg:.3f} (reliability {score})")
    print("current roster:", " ".join(f"{k}={v}" for k, v in sorted(roster.items(), key=lambda x: -x[1])))
    if score > weakest:
        verdict = "ROSTER-WORTHY"
    elif score >= weakest - 0.10:
        verdict = "VOTE-FODDER (near-roster; only add if it's a genuinely new family)"
    else:
        verdict = "REJECT"
    print("VERDICT:", verdict)

    if commit:
        if verdict == "REJECT":
            sys.exit("refusing to --commit a REJECT: the mechanism only registers measured winners")
        table.setdefault(lang, {})[slug] = score
        json.dump(table, open(rel_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"committed reliability: {lang}/{slug} = {score}")
        if model not in BUILTIN:
            print(f"NOTE: wire the loader — add '{slug}' to consensus.FAMILY (own family) and a "
                  f"_witness_call branch (or acoustic2._MODELS for wav2vec2-family) before adding "
                  f"'{slug}' to ROSTER['{lang}'].")


if __name__ == "__main__":
    main()
