#!/usr/bin/env python3
"""Full-parity battery: hard clips + ground truth for ALL languages with a `say` voice (13/14 —
Urdu has no macOS voice). Proper-noun + number dense sentence read by a native voice with additive
pink noise, so the witnesses genuinely disagree. This is what lets us hold EVERY language to the
same measured bar, not a slice. Prefix `fp_<lang>_`. Ground truth = the exact synthesized text.
"""
import os, subprocess, json

BAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")
os.makedirs(BAT, exist_ok=True)

# lang -> (voice, sentence). Each: names + a number, the accuracy frontier.
CLIPS = {
    "en": ("Alex",    "Doctor Nguyen sent forty-seven thousand euros to the Kagiso account in Reykjavik on the third of March."),
    "es": ("Mónica",  "La doctora Nguyen envió cuarenta y siete mil euros a la cuenta de Kagiso en Guadalajara el tres de marzo."),
    "fr": ("Thomas",  "Le docteur Nguyen a envoyé quarante-sept mille euros vers le compte de Kagiso à Marseille le trois mars."),
    "de": ("Anna",    "Doktor Nguyen sandte siebenundvierzigtausend Euro an das Konto von Kagiso in München am dritten März."),
    "pt": ("Luciana", "A doutora Nguyen enviou quarenta e sete mil euros para a conta de Kagiso em Lisboa no dia três de março."),
    "ru": ("Milena",  "Доктор Нгуен отправил сорок семь тысяч евро на счёт Кагисо в Новосибирске третьего марта."),
    "ja": ("Kyoko",   "グエン医師はレイキャビクのカギソの口座に四万七千ユーロを三月三日に送金しました。"),
    "ko": ("Yuna",    "응우옌 박사가 레이캬비크에 있는 카기소 계좌로 사만 칠천 유로를 삼월 삼일에 보냈습니다."),
    "vi": ("Linh",    "Bác sĩ Nguyễn đã gửi bốn mươi bảy nghìn euro vào tài khoản Kagiso ở Marseille vào ngày ba tháng ba."),
    "ar": ("Majed",   "أرسل الطبيب نجوين سبعة وأربعين ألف يورو إلى حساب كاغيسو في مرسيليا في الثالث من مارس."),
    "hi": ("Lekha",   "डॉक्टर नगुयेन ने मार्सिले में कागिसो के खाते में सैंतालीस हज़ार यूरो तीन मार्च को भेजे।"),
    "tr": ("Yelda",   "Doktor Nguyen üç Mart'ta Marsilya'daki Kagiso hesabına kırk yedi bin euro gönderdi."),
    "uk": ("Lesya",   "Лікар Нгуєн надіслав сорок сім тисяч євро на рахунок Кагісо в Новосибірську третього березня."),
}


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def build(lang, voice, text):
    aiff = os.path.join(BAT, f"_fp_{lang}.aiff")
    subprocess.run(["say", "-v", voice, "-r", "175", "-o", aiff, text], check=True)
    clean = os.path.join(BAT, f"_fp_{lang}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", aiff, "-ac", "1", "-ar", "16000", clean,
                    "-loglevel", "error"], check=True)
    d = _dur(clean)
    out = os.path.join(BAT, f"fp_{lang}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", clean, "-f", "lavfi", "-t", f"{d:.2f}",
                    "-i", "anoisesrc=color=pink:amplitude=0.15",
                    "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.85[a]",
                    "-map", "[a]", "-ac", "1", "-ar", "16000", out, "-loglevel", "error"], check=True)
    os.remove(aiff); os.remove(clean)
    with open(os.path.join(BAT, f"fp_{lang}.json"), "w", encoding="utf-8") as fh:
        json.dump({"text": text, "lang": lang,
                   "speakers": [{"start": 0.0, "end": round(d, 2), "speaker": "A"}]},
                  fh, ensure_ascii=False, indent=1)
    print(f"  fp_{lang:3} ({voice:8}) {d:.1f}s")


if __name__ == "__main__":
    have = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    print("generating full-parity battery (13 langs; ur has no macOS voice)...")
    for lang, (voice, text) in CLIPS.items():
        if voice in have:
            build(lang, voice, text)
        else:
            print(f"  fp_{lang}: SKIP (voice {voice!r} missing)")
    print("done -> bench/battery/fp_<lang>.wav (+ .json)")
