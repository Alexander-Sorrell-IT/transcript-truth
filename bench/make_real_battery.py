#!/usr/bin/env python3
"""Phase IV — REAL-audio battery from FLEURS (real human speech, human-verified transcripts).
Streams N clips per language (no full-dataset download), writes bench/battery_real/rl_<lang><i>.wav
+ .json in the same shape as the TTS battery so every existing ruler works unchanged.

    python3 bench/make_real_battery.py [n_per_lang] [lang ...]
"""
import os, sys, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "bench", "battery_real")
os.makedirs(OUT, exist_ok=True)

FLEURS = {  # our code -> FLEURS config
    "en": "en_us", "ja": "ja_jp", "es": "es_419", "fr": "fr_fr", "de": "de_de",
    "pt": "pt_br", "ru": "ru_ru", "uk": "uk_ua", "ko": "ko_kr", "tr": "tr_tr",
    "vi": "vi_vn", "ar": "ar_eg", "hi": "hi_in", "ur": "ur_pk",
}

n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 15
langs = [a for a in sys.argv[1:] if not a.isdigit()] or ["tr", "ar", "hi", "ur", "vi", "en", "ja"]

import soundfile as sf
from datasets import load_dataset

for lang in langs:
    cfg = FLEURS[lang]
    print(f"[{lang}] streaming {cfg} …", flush=True)
    ds = load_dataset("google/fleurs", cfg, split="test", streaming=True,
                      trust_remote_code=True)
    got = 0
    for ex in ds:
        # keep mid-length clips (4-15s): long enough to be real, short enough to bench cheaply
        audio = ex["audio"]
        dur = len(audio["array"]) / audio["sampling_rate"]
        if not (4.0 <= dur <= 15.0):
            continue
        stem = f"rl_{lang}{chr(97 + got)}"
        sf.write(os.path.join(OUT, stem + ".wav"), audio["array"], audio["sampling_rate"])
        json.dump({"text": ex["transcription"], "lang": lang, "src": "fleurs",
                   "duration": round(dur, 1)},
                  open(os.path.join(OUT, stem + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        got += 1
        print(f"  {stem} {dur:.1f}s", flush=True)
        if got >= n:
            break
    print(f"[{lang}] {got} clips", flush=True)
print("done ->", OUT)
