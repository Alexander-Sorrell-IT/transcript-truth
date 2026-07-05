#!/usr/bin/env python3
"""Battery set 3: +3 hard clips per language (tags e/f/g) -> 7 clips/lang total, sharpening the
measured reliability weights (more clips = less variance in 1-mean(WER)). Same recipe: native
`say` voice + pink noise; ground truth = the exact synthesized text."""
import os, subprocess, json

BAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "battery")

CLIPS = {
    "en": ("Alex", [
        "Captain Adebayo delivered sixty-five packages to the Lindqvist office in Casablanca on the eleventh of August.",
        "Doctor Petrescu examined thirty-one patients at the Kilimanjaro clinic with nurse Yamamoto on the second of May.",
        "Engineer Novák installed nineteen turbines near the Oaxaca plant for the Björklund company on the eighth of October.",
    ]),
    "es": ("Mónica", [
        "El capitán Adebayo entregó sesenta y cinco paquetes a la oficina Lindqvist en Casablanca el once de agosto.",
        "La doctora Petrescu examinó treinta y un pacientes en la clínica del Kilimanjaro con la enfermera Yamamoto el dos de mayo.",
        "El ingeniero Novák instaló diecinueve turbinas cerca de la planta de Oaxaca para la empresa Björklund el ocho de octubre.",
    ]),
    "fr": ("Thomas", [
        "Le capitaine Adebayo a livré soixante-cinq colis au bureau Lindqvist à Casablanca le onze août.",
        "Le docteur Petrescu a examiné trente et un patients à la clinique du Kilimandjaro avec l'infirmière Yamamoto le deux mai.",
        "L'ingénieur Novák a installé dix-neuf turbines près de l'usine d'Oaxaca pour la société Björklund le huit octobre.",
    ]),
    "de": ("Anna", [
        "Kapitän Adebayo lieferte fünfundsechzig Pakete an das Lindqvist-Büro in Casablanca am elften August.",
        "Doktor Petrescu untersuchte einunddreißig Patienten in der Kilimandscharo-Klinik mit Schwester Yamamoto am zweiten Mai.",
        "Ingenieur Novák installierte neunzehn Turbinen nahe dem Oaxaca-Werk für die Firma Björklund am achten Oktober.",
    ]),
    "pt": ("Luciana", [
        "O capitão Adebayo entregou sessenta e cinco pacotes ao escritório Lindqvist em Casablanca no dia onze de agosto.",
        "A doutora Petrescu examinou trinta e um pacientes na clínica do Kilimanjaro com a enfermeira Yamamoto no dia dois de maio.",
        "O engenheiro Novák instalou dezenove turbinas perto da fábrica de Oaxaca para a empresa Björklund no dia oito de outubro.",
    ]),
    "ru": ("Milena", [
        "Капитан Адебайо доставил шестьдесят пять посылок в офис Линдквиста в Касабланке одиннадцатого августа.",
        "Доктор Петреску осмотрел тридцать одного пациента в клинике Килиманджаро с медсестрой Ямамото второго мая.",
        "Инженер Новак установил девятнадцать турбин возле завода в Оахаке для компании Бьёрклунд восьмого октября.",
    ]),
    "ja": ("Kyoko", [
        "アデバヨ船長は八月十一日にカサブランカのリンドクヴィスト事務所へ六十五個の荷物を届けました。",
        "ペトレスク医師は五月二日に山本看護師とキリマンジャロ診療所で三十一人の患者を診察しました。",
        "ノヴァーク技師は十月八日にビョルクルンド社のためオアハカ工場の近くに十九基のタービンを設置しました。",
    ]),
    "ko": ("Yuna", [
        "아데바요 선장은 팔월 십일일에 카사블랑카의 린드크비스트 사무소로 예순다섯 개의 소포를 배달했습니다.",
        "페트레스쿠 박사는 오월 이일에 야마모토 간호사와 킬리만자로 진료소에서 서른한 명의 환자를 진찰했습니다.",
        "노바크 기사는 시월 팔일에 비외르클룬드 회사를 위해 오악사카 공장 근처에 열아홉 개의 터빈을 설치했습니다.",
    ]),
    "vi": ("Linh", [
        "Thuyền trưởng Adebayo đã giao sáu mươi lăm gói hàng đến văn phòng Lindqvist ở Casablanca vào ngày mười một tháng tám.",
        "Bác sĩ Petrescu đã khám ba mươi mốt bệnh nhân tại phòng khám Kilimanjaro cùng y tá Yamamoto vào ngày hai tháng năm.",
        "Kỹ sư Novák đã lắp mười chín tua bin gần nhà máy Oaxaca cho công ty Björklund vào ngày tám tháng mười.",
    ]),
    "ar": ("Majed", [
        "سلّم الكابتن أديبايو خمسة وستين طرداً إلى مكتب ليندكفيست في الدار البيضاء في الحادي عشر من أغسطس.",
        "فحص الدكتور بيتريسكو واحداً وثلاثين مريضاً في عيادة كليمنجارو مع الممرضة ياماموتو في الثاني من مايو.",
        "ركّب المهندس نوفاك تسعة عشر توربيناً قرب مصنع أواكساكا لشركة بيوركلوند في الثامن من أكتوبر.",
    ]),
    "hi": ("Lekha", [
        "कप्तान अदेबायो ने ग्यारह अगस्त को कासाब्लांका के लिंडक्विस्ट कार्यालय में पैंसठ पार्सल पहुँचाए।",
        "डॉक्टर पेत्रेस्कु ने दो मई को नर्स यामामोतो के साथ किलिमंजारो क्लिनिक में इकतीस मरीज़ों की जाँच की।",
        "इंजीनियर नोवाक ने आठ अक्टूबर को ब्योर्कलुंड कंपनी के लिए ओआहाका संयंत्र के पास उन्नीस टरबाइन लगाए।",
    ]),
    "tr": ("Yelda", [
        "Kaptan Adebayo on bir Ağustos'ta Kazablanka'daki Lindqvist ofisine altmış beş paket teslim etti.",
        "Doktor Petrescu iki Mayıs'ta hemşire Yamamoto ile Kilimanjaro kliniğinde otuz bir hastayı muayene etti.",
        "Mühendis Novák sekiz Ekim'de Björklund şirketi için Oaxaca fabrikasının yakınına on dokuz türbin kurdu.",
    ]),
    "uk": ("Lesya", [
        "Капітан Адебайо доставив шістдесят п'ять посилок до офісу Ліндквіста в Касабланці одинадцятого серпня.",
        "Лікар Петреску оглянув тридцять одного пацієнта в клініці Кіліманджаро з медсестрою Ямамото другого травня.",
        "Інженер Новак встановив дев'ятнадцять турбін біля заводу в Оахаці для компанії Бьорклунд восьмого жовтня.",
    ]),
}

SUFFIX = ["e", "f", "g"]
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_full_parity_battery2 import build  # same synth recipe

if __name__ == "__main__":
    have = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    for lang, (voice, texts) in CLIPS.items():
        if voice not in have:
            print(f"  {lang}: voice {voice} missing — skipped")
            continue
        for tag, text in zip(SUFFIX, texts):
            build(lang, voice, text, tag)
