#!/usr/bin/env python3
"""Urdu battery — the one language with ZERO measurements (macOS `say` has no Urdu voice).
Synthesizes with espeak-ng (installed via brew) + the same pink-noise treatment as every other
language, so Urdu is finally held to the same measured bar. 7 clips = same sentences as the rest."""
import os, subprocess, json

BAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")

SENTS = {
    "":  "ڈاکٹر نگوین نے مارسیلز میں کاگیسو کے کھاتے میں سینتالیس ہزار یورو تین مارچ کو بھیجے۔",
    "b": "پروفیسر اوکونکوو نے نو جولائی کو لیوبلیانا کی برگسٹروم فاؤنڈیشن کو بارہ ہزار ڈالر منتقل کیے۔",
    "c": "مس تاکاہاشی نے پانچ جون کو مراکش کے ہوٹل میں ناکامورا وفد کے لیے تئیس کمرے بک کیے۔",
    "d": "مسٹر فرنانڈیز نے یکم اپریل کو والپارائیسو سے گدانسک کے کوالسکی گودام کو آٹھ سو صندوق بھیجے۔",
    "e": "کپتان ادیبایو نے گیارہ اگست کو کاسابلانکا کے لنڈکوسٹ دفتر میں پینسٹھ پارسل پہنچائے۔",
    "f": "ڈاکٹر پیٹریسکو نے دو مئی کو نرس یاماموتو کے ساتھ کلیمنجارو کلینک میں اکتیس مریضوں کا معائنہ کیا۔",
    "g": "انجینئر نوواک نے آٹھ اکتوبر کو بیورکلنڈ کمپنی کے لیے اواہاکا پلانٹ کے قریب انیس ٹربائنیں لگائیں۔",
}


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


for tag, text in SENTS.items():
    raw = os.path.join(BAT, f"_fp_ur{tag}.wav")
    subprocess.run(["espeak-ng", "-v", "ur", "-s", "150", "-w", raw, text], check=True)
    clean = os.path.join(BAT, f"_fp_ur{tag}_16k.wav")
    subprocess.run(["ffmpeg", "-y", "-i", raw, "-ac", "1", "-ar", "16000", clean,
                    "-loglevel", "error"], check=True)
    d = _dur(clean)
    out = os.path.join(BAT, f"fp_ur{tag}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", clean, "-f", "lavfi", "-t", f"{d:.2f}",
                    "-i", "anoisesrc=color=pink:amplitude=0.15",
                    "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.85[a]",
                    "-map", "[a]", "-ac", "1", "-ar", "16000", out, "-loglevel", "error"], check=True)
    os.remove(raw); os.remove(clean)
    with open(os.path.join(BAT, f"fp_ur{tag}.json"), "w", encoding="utf-8") as fh:
        json.dump({"text": text, "lang": "ur",
                   "speakers": [{"start": 0.0, "end": round(d, 2), "speaker": "A"}]},
                  fh, ensure_ascii=False, indent=1)
    print(f"fp_ur{tag or 'a'} {d:.1f}s", flush=True)
