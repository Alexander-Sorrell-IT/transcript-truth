#!/usr/bin/env python3
"""Build <lang>_confirmed.json (homophone trap-sets) for the 9 languages that lack them —
DETERMINISTICALLY: phonemize each language's frequent vocabulary (wordfreq top-N) with espeak-ng
G2P and group words that share an IPA pronunciation. No model proposes anything; the phonetics
engine IS the authority. Same shape decision.py / en_rules consume:
  [{key, reading, options: [{word, gloss}], note}]

Run: python3 bench/build_confirmed_multilang.py [lang ...]  (default: the 9 missing)
Env: TOP_N (default 25000), MIN_ZIPF (default 2.5)
"""
import os, sys, json, glob, collections

os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY",
                      (glob.glob("/opt/homebrew/Cellar/espeak-ng/*/lib/libespeak-ng.dylib") + [""])[0])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP_N = int(os.environ.get("TOP_N", "25000"))
MIN_ZIPF = float(os.environ.get("MIN_ZIPF", "2.5"))

# espeak voice per language (phonemizer language codes)
VOICE = {"fr": "fr-fr", "de": "de", "pt": "pt", "tr": "tr", "ko": "ko",
         "vi": "vi", "ar": "ar", "hi": "hi", "ur": "ur"}

# native-script filter — wordfreq lists carry Latin loanword junk ('box' in tr, 'app' in ko)
# that G2P groups into garbage trap-sets; only the language's own script belongs here.
import re as _re
SCRIPT = {
    "fr": r"[a-zà-ÿœæ]+", "de": r"[a-zäöüß]+", "pt": r"[a-zà-ÿ]+", "tr": r"[a-zçğıöşü]+",
    "vi": r"[a-zà-ỹăâđêôơư]+", "ko": r"[가-힣]+", "hi": r"[ऀ-ॿ]+",
    "ar": r"[؀-ۿ]+", "ur": r"[؀-ۿ]+",
}

# Arabic-script languages: espeak misreads bare spelling variants (it SPELLS OUT alef maqsurah),
# but the real ASR traps ARE the orthographic variants — hamza seats, taa marbuta, final ya.
# Group by deterministic normalization instead of G2P (standard Arabic-NLP normalization).
_AR_NORM = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه",
                          "ؤ": "و", "ئ": "ي", "ٹ": "ت", "ک": "ك", "ی": "ي", "ہ": "ه", "ے": "ي"})


def _ar_key(w):
    return w.translate(_AR_NORM)


def build(lang):
    from wordfreq import top_n_list, zipf_frequency
    from phonemizer import phonemize
    rx = _re.compile(f"^{SCRIPT[lang]}$")
    words = [w for w in top_n_list(lang, TOP_N)
             if len(w) >= 2 and rx.match(w) and zipf_frequency(w, lang) >= MIN_ZIPF]
    groups = collections.defaultdict(list)
    if lang in ("ar", "ur"):
        print(f"[{lang}] {len(words)} vocab words -> orthographic normalization ...", flush=True)
        for w in words:
            groups[_ar_key(w)].append(w)
    else:
        print(f"[{lang}] {len(words)} vocab words -> G2P ...", flush=True)
        ipas = phonemize(words, language=VOICE[lang], backend="espeak", strip=True, njobs=4)
        for w, ipa in zip(words, ipas):
            ipa = ipa.strip().replace("ˈ", "").replace("ˌ", "")   # stress-insensitive
            if ipa:
                groups[ipa].append(w)

    out = []
    for ipa, members in groups.items():
        uniq = sorted(set(members))
        if len(uniq) < 2:
            continue
        # Latin scripts only: drop pure case/diacritic-duplicates (not real traps). The ASCII
        # collapse would erase non-Latin words entirely and falsely kill every set.
        if lang not in ("ko", "hi", "ar", "ur"):
            import unicodedata
            base = {unicodedata.normalize("NFKD", m).encode("ascii", "ignore").decode().lower()
                    for m in uniq}
            if len(base) < 2:
                continue
        out.append({"key": "/".join(uniq), "reading": ipa,
                    "options": [{"word": m, "gloss": ""} for m in uniq],
                    "note": "same espeak-ng pronunciation — ASR homophone trap (auto-derived)"})
    out.sort(key=lambda e: e["key"])
    path = os.path.join(ROOT, "data", f"{lang}_confirmed.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"[{lang}] DONE: {len(out)} trap-sets -> {path}", flush=True)


if __name__ == "__main__":
    langs = sys.argv[1:] or list(VOICE)
    for lang in langs:
        try:
            build(lang)
        except Exception as e:
            print(f"[{lang}] FAILED: {e}", flush=True)
