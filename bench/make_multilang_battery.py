#!/usr/bin/env python3
"""Hard clips + ground truth in multiple languages (macOS `say` voices + ffmpeg pink noise).

Phase II: prove the consensus/brain per language, not just English. Each clip is a proper-noun +
number dense sentence (the case that stresses the deterministic judge) read by a native voice with
additive noise, so the witnesses genuinely disagree. Prefix `ml_<lang>_`. Ground truth is the exact
synthesized text. Only languages with a usable `say` voice on this machine are generated.
"""
import os, subprocess, json, shutil

BAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")
os.makedirs(BAT, exist_ok=True)

# lang -> (say voice, sentence). Proper nouns + numbers = the accuracy frontier.
CLIPS = {
    "es": ("Mónica", "La ministra Ndiaye transfirió cuarenta y siete mil euros a la cuenta "
                       "de Xiomara en Guadalajara el tres de marzo."),
    "fr": ("Thomas", "Le docteur Nguyen et madame Okonkwo ont viré quarante-sept mille euros "
                       "vers le compte de Kagiso à Marseille le trois mars."),
    "de": ("Anna", "Doktor Nguyen und Frau Okonkwo überwiesen siebenundvierzigtausend Euro "
                     "auf das Konto von Kagiso in München am dritten März."),
    "pt": ("Luciana", "A doutora Nguyen transferiu quarenta e sete mil euros para a conta "
                        "de Kagiso em Lisboa no dia três de março."),
    "ru": ("Milena", "Доктор Нгуен перевёл сорок семь тысяч евро на счёт Ксении "
                      "в Новосибирске третьего марта."),
    "ja": ("Kyoko", "グエン医師はミュンヘンのカギソの口座に四万七千ユーロを三月三日に送金しました。"),
    "ko": ("Yuna", "응우옌 박사가 뮌헨에 있는 카기소 계좌로 사만 칠천 유로를 삼월 삼일에 송금했습니다."),
}


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def build(lang, voice, text):
    aiff = os.path.join(BAT, f"_ml_{lang}.aiff")
    subprocess.run(["say", "-v", voice, "-r", "175", "-o", aiff, text], check=True)
    clean = os.path.join(BAT, f"_ml_{lang}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", aiff, "-ac", "1", "-ar", "16000", clean,
                    "-loglevel", "error"], check=True)
    d = _dur(clean)
    out = os.path.join(BAT, f"ml_{lang}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", clean, "-f", "lavfi", "-t", f"{d:.2f}",
                    "-i", "anoisesrc=color=pink:amplitude=0.15",
                    "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.85[a]",
                    "-map", "[a]", "-ac", "1", "-ar", "16000", out, "-loglevel", "error"], check=True)
    os.remove(aiff); os.remove(clean)
    with open(os.path.join(BAT, f"ml_{lang}.json"), "w", encoding="utf-8") as fh:
        json.dump({"text": text, "lang": lang,
                   "speakers": [{"start": 0.0, "end": round(d, 2), "speaker": "A"}]},
                  fh, ensure_ascii=False, indent=1)
    print(f"  ml_{lang:3} ({voice:8}) {d:.1f}s")


def available_voices():
    have = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    return have


if __name__ == "__main__":
    have = available_voices()
    print("generating multilingual hard clips...")
    for lang, (voice, text) in CLIPS.items():
        if voice in have:
            build(lang, voice, text)
        else:
            print(f"  ml_{lang}: SKIP (voice {voice!r} not installed)")
    print("done -> bench/battery/ml_<lang>.wav (+ .json)")
