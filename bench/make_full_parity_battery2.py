#!/usr/bin/env python3
"""Battery EXTENSION: 3 more hard clips per language (different proper nouns + numbers each), so
per-witness reliability is measured on 4 clips/lang instead of 1 — enough to derive per-language
reliability weights without tuning on a single sentence. Same recipe as make_full_parity_battery.py
(native `say` voice + pink noise). Files: fp_<lang>b/c/d.{wav,json} — the live runner globs fp_*.
"""
import os, subprocess, json

BAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")
os.makedirs(BAT, exist_ok=True)

# lang -> (voice, [3 sentences]) — names + numbers, the accuracy frontier, varied per clip.
CLIPS = {
    "en": ("Alex", [
        "Professor Okonkwo transferred twelve thousand dollars to the Bergström foundation in Ljubljana on the ninth of July.",
        "Miss Takahashi booked twenty-three rooms at the Marrakesh hotel for the Nakamura delegation on the fifth of June.",
        "Mister Fernandez shipped eight hundred crates from Valparaíso to the Kowalski warehouse in Gdańsk on the first of April.",
    ]),
    "es": ("Mónica", [
        "El profesor Okonkwo transfirió doce mil dólares a la fundación Bergström en Liubliana el nueve de julio.",
        "La señorita Takahashi reservó veintitrés habitaciones en el hotel de Marrakech para la delegación Nakamura el cinco de junio.",
        "El señor Fernández envió ochocientas cajas desde Valparaíso al almacén Kowalski en Gdansk el primero de abril.",
    ]),
    "fr": ("Thomas", [
        "Le professeur Okonkwo a transféré douze mille dollars à la fondation Bergström à Ljubljana le neuf juillet.",
        "Mademoiselle Takahashi a réservé vingt-trois chambres à l'hôtel de Marrakech pour la délégation Nakamura le cinq juin.",
        "Monsieur Fernandez a expédié huit cents caisses de Valparaíso à l'entrepôt Kowalski à Gdansk le premier avril.",
    ]),
    "de": ("Anna", [
        "Professor Okonkwo überwies zwölftausend Dollar an die Bergström-Stiftung in Ljubljana am neunten Juli.",
        "Fräulein Takahashi buchte dreiundzwanzig Zimmer im Hotel in Marrakesch für die Nakamura-Delegation am fünften Juni.",
        "Herr Fernandez verschickte achthundert Kisten von Valparaíso zum Kowalski-Lager in Danzig am ersten April.",
    ]),
    "pt": ("Luciana", [
        "O professor Okonkwo transferiu doze mil dólares para a fundação Bergström em Liubliana no dia nove de julho.",
        "A senhorita Takahashi reservou vinte e três quartos no hotel de Marraquexe para a delegação Nakamura no dia cinco de junho.",
        "O senhor Fernandes enviou oitocentas caixas de Valparaíso para o armazém Kowalski em Gdansk no primeiro de abril.",
    ]),
    "ru": ("Milena", [
        "Профессор Оконкво перевёл двенадцать тысяч долларов в фонд Бергстрёма в Любляне девятого июля.",
        "Госпожа Такахаси забронировала двадцать три номера в отеле Марракеша для делегации Накамуры пятого июня.",
        "Господин Фернандес отправил восемьсот ящиков из Вальпараисо на склад Ковальского в Гданьске первого апреля.",
    ]),
    "ja": ("Kyoko", [
        "オコンクォ教授は七月九日にリュブリャナのベルグストロム財団に一万二千ドルを送金しました。",
        "高橋さんは六月五日にマラケシュのホテルに中村代表団のため二十三室を予約しました。",
        "フェルナンデスさんは四月一日にバルパライソからグダニスクのコワルスキ倉庫へ八百箱を発送しました。",
    ]),
    "ko": ("Yuna", [
        "오콘쿼 교수는 칠월 구일에 류블랴나의 베리스트룀 재단으로 만 이천 달러를 송금했습니다.",
        "다카하시 씨는 유월 오일에 마라케시 호텔에 나카무라 대표단을 위해 스물세 개의 방을 예약했습니다.",
        "페르난데스 씨는 사월 일일에 발파라이소에서 그단스크의 코발스키 창고로 팔백 상자를 보냈습니다.",
    ]),
    "vi": ("Linh", [
        "Giáo sư Okonkwo đã chuyển mười hai nghìn đô la cho quỹ Bergström ở Ljubljana vào ngày chín tháng bảy.",
        "Cô Takahashi đã đặt hai mươi ba phòng tại khách sạn Marrakesh cho đoàn Nakamura vào ngày năm tháng sáu.",
        "Ông Fernandez đã gửi tám trăm thùng hàng từ Valparaíso đến kho Kowalski ở Gdansk vào ngày một tháng tư.",
    ]),
    "ar": ("Majed", [
        "حوّل البروفيسور أوكونكو اثني عشر ألف دولار إلى مؤسسة بيرغستروم في ليوبليانا في التاسع من يوليو.",
        "حجزت الآنسة تاكاهاشي ثلاثاً وعشرين غرفة في فندق مراكش لوفد ناكامورا في الخامس من يونيو.",
        "أرسل السيد فرنانديز ثمانمائة صندوق من فالبارايسو إلى مستودع كوفالسكي في غدانسك في الأول من أبريل.",
    ]),
    "hi": ("Lekha", [
        "प्रोफेसर ओकोनकवो ने नौ जुलाई को ल्युब्लियाना के बर्गस्ट्रॉम फाउंडेशन को बारह हज़ार डॉलर भेजे।",
        "सुश्री ताकाहाशी ने पाँच जून को मराकेश के होटल में नाकामुरा प्रतिनिधिमंडल के लिए तेईस कमरे बुक किए।",
        "श्री फर्नांडेज़ ने एक अप्रैल को वालपराइसो से ग्दान्स्क के कोवाल्स्की गोदाम को आठ सौ बक्से भेजे।",
    ]),
    "tr": ("Yelda", [
        "Profesör Okonkwo dokuz Temmuz'da Ljubljana'daki Bergström vakfına on iki bin dolar gönderdi.",
        "Bayan Takahashi beş Haziran'da Marakeş'teki otelde Nakamura heyeti için yirmi üç oda ayırttı.",
        "Bay Fernandez bir Nisan'da Valparaíso'dan Gdansk'taki Kowalski deposuna sekiz yüz kasa gönderdi.",
    ]),
    "uk": ("Lesya", [
        "Професор Оконкво переказав дванадцять тисяч доларів фонду Бергстрема в Любляні дев'ятого липня.",
        "Пані Такахасі забронювала двадцять три номери в готелі Марракеша для делегації Накамури п'ятого червня.",
        "Пан Фернандес відправив вісімсот ящиків з Вальпараїсо на склад Ковальського у Гданську першого квітня.",
    ]),
}

SUFFIX = ["b", "c", "d"]


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def build(lang, voice, text, tag):
    aiff = os.path.join(BAT, f"_fp_{lang}{tag}.aiff")
    subprocess.run(["say", "-v", voice, "-r", "175", "-o", aiff, text], check=True)
    clean = os.path.join(BAT, f"_fp_{lang}{tag}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", aiff, "-ac", "1", "-ar", "16000", clean,
                    "-loglevel", "error"], check=True)
    d = _dur(clean)
    out = os.path.join(BAT, f"fp_{lang}{tag}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", clean, "-f", "lavfi", "-t", f"{d:.2f}",
                    "-i", "anoisesrc=color=pink:amplitude=0.15",
                    "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.85[a]",
                    "-map", "[a]", "-ac", "1", "-ar", "16000", out, "-loglevel", "error"], check=True)
    os.remove(aiff); os.remove(clean)
    with open(os.path.join(BAT, f"fp_{lang}{tag}.json"), "w", encoding="utf-8") as fh:
        json.dump({"text": text, "lang": lang,
                   "speakers": [{"start": 0.0, "end": round(d, 2), "speaker": "A"}]},
                  fh, ensure_ascii=False, indent=1)
    print(f"  fp_{lang}{tag} ({voice}) {d:.1f}s", flush=True)


if __name__ == "__main__":
    have = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    for lang, (voice, texts) in CLIPS.items():
        if voice not in have:
            print(f"  {lang}: voice {voice} missing — skipped")
            continue
        for tag, text in zip(SUFFIX, texts):
            build(lang, voice, text, tag)
