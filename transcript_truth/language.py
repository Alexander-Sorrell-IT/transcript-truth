"""Per-segment language detection (deterministic, by script). Splits a mixed
Japanese/English line into same-language runs so each run can be routed to the
right verification catalog: Japanese runs -> kana/JP-homophone/coherence checks,
English runs -> EN-homophone/formatting checks. No model.
"""
import re

_JP = re.compile(r"[぀-ヿ一-鿿々〆ー]")   # hiragana, katakana, kanji, ー
_LATIN = re.compile(r"[A-Za-z]")
_CYR = re.compile(r"[Ѐ-ӿ]")        # Cyrillic (ru/uk)
_HANGUL = re.compile(r"[가-힣]")     # Korean
_ARABIC = re.compile(r"[؀-ۿ]")     # Arabic/Urdu
_DEVA = re.compile(r"[ऀ-ॿ]")       # Devanagari (Hindi)

# lang code -> the deterministic profile that audits it (see transcript_truth.profiles).
# New languages auto-route here the moment their profile is registered.
PROFILE_FOR = {"ja": "default", "en": "en", "es": "es", "ru": "ru", "uk": "uk",
               "de": "de", "fr": "fr", "pt": "pt", "tr": "tr", "vi": "vi",
               "ko": "ko", "ar": "ar", "hi": "hi", "ur": "ur"}


def profile_for(lang):
    """Map a detected language code to its audit profile (falls back to 'default')."""
    return PROFILE_FOR.get((lang or "").split("-")[0].lower(), "default")


def _detect_slice(audio_path, slice_s):
    """Cut the first `slice_s` seconds for cheap detection. Returns (path, tmp_or_None)."""
    from . import chunking
    if chunking.have_ffmpeg() and (chunking.probe(audio_path)[0] or 0) > slice_s:
        import os, subprocess, tempfile
        fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="ttdetect_"); os.close(fd)
        try:
            subprocess.run(["ffmpeg", "-y", "-t", str(slice_s), "-i", audio_path,
                            "-ac", "1", "-ar", "16000", tmp, "-loglevel", "error"], check=True)
            return tmp, tmp
        except Exception:
            return audio_path, None
    return audio_path, None


def detect_multi(audio_path, slice_s=45):
    """Two-detector language id (MODEL_MAP.md Stage 0): Deepgram + free local Whisper, so ONE
    detector can't misroute the whole job. Returns {lang, candidates, agree, deepgram, whisper}:
    `lang` is Deepgram's read (primary) with Whisper as fallback; `agree` is True when both name
    the same language; `candidates` lists every language named so the caller can try both rosters."""
    from . import witness
    probe_path, tmp = _detect_slice(audio_path, slice_s)
    try:
        d = witness.deepgram_detect_language(probe_path) or ""
        w = witness.whisper_detect_language(probe_path) or ""
    finally:
        if tmp and __import__("os").path.exists(tmp):
            __import__("os").remove(tmp)
    return {"lang": d or w, "candidates": sorted({c for c in (d, w) if c}),
            "agree": bool(d and w and d == w), "deepgram": d, "whisper": w}


def detect(audio_path, slice_s=45):
    """Best single language code (Deepgram primary, Whisper fallback). See detect_multi for the
    agreement/candidates a caller can act on."""
    return detect_multi(audio_path, slice_s)["lang"]


def route(audio_path):
    """Detect language and return the routing decision: {lang, profile, roster, candidates,
    detect_agree}. When the two detectors DISAGREE, `candidates` holds both so the caller can
    run both rosters and pick by first-pass agreement instead of trusting one detector."""
    from .consensus import ROSTER
    d = detect_multi(audio_path)
    lang = d["lang"]
    return {"lang": lang, "profile": profile_for(lang), "roster": ROSTER.get(lang, []),
            "candidates": d["candidates"], "detect_agree": d["agree"]}


def script_of(ch):
    """Coarse script class of a single character (for per-turn language tagging)."""
    if _JP.search(ch):
        return "ja"
    if _HANGUL.search(ch):
        return "ko"
    if _CYR.search(ch):
        return "cyr"      # ru/uk share a script — splitting them needs a model (code-switching phase)
    if _ARABIC.search(ch):
        return "ar"       # ar/ur share a script
    if _DEVA.search(ch):
        return "hi"
    if _LATIN.search(ch):
        return "en"       # en/es/de/fr/pt/tr share a script
    return None


def lang_of(text):
    """'ja' if the text is mostly Japanese script, 'en' if mostly Latin, else 'mixed'."""
    j = len(_JP.findall(text))
    e = len(_LATIN.findall(text))
    if j and j >= e:
        return "ja"
    if e and e > j:
        return "en"
    return "ja" if j else "en" if e else "neutral"


_KATA_RUN = re.compile(r"[ァ-ヶ][ァ-ヶー・]{6,}")  # katakana run >= 7 chars

# Short katakana that are conversational English, not Japanese content. CLEAR = essentially
# never used as a Japanese word -> flag anywhere. CHECK = also a real loanword (ライト=light) ->
# only flag in a bilingual line (English present), so monolingual JP files don't false-fire.
_KATA_EN_CLEAR = {"オーマイゴッド": "Oh my God", "オーマイガッド": "Oh my God", "サンキュー": "thank you",
                  "ハロー": "hello", "ハロウ": "hello", "ソーリー": "sorry", "プリーズ": "please",
                  "イエス": "yes", "ウェル": "well", "ファニー": "funny"}
_KATA_EN_CHECK = {"ライト": "Right", "グッド": "good", "ナイス": "nice", "ノー": "no",
                  "オーケー": "okay", "オッケー": "okay", "イングリッシュ": "English", "ムービー": "movie"}


def untranslated_english(t):
    """Flag katakana that's really spoken English, not Japanese — both long non-dictionary
    runs (アイラブディスムービー) and short conversational ones (オーマイゴッド, ライト).
    Deterministic, so it catches what the stitching model misses. Real loanwords are guarded:
    dictionary words for long runs, bilingual-context gate for short ones."""
    from .verdict import gloss
    from .types import Flag
    out = []
    for ln in t.lines:
        for m in _KATA_RUN.finditer(ln.text):
            run = m.group(0)
            if not gloss(run):
                out.append(Flag(
                    rule="untranslated_english", severity="review", line=ln.n, evidence=run,
                    label=f'long katakana "{run[:24]}" — likely English spoken, transcribe as English',
                    fix="Replace katakana-English with the actual English words from the English-mode read."))
        has_en = bool(_LATIN.search(ln.text))  # bilingual line?
        for kata, eng in _KATA_EN_CLEAR.items():
            if kata in ln.text:
                out.append(Flag(rule="untranslated_english", severity="review", line=ln.n, evidence=kata,
                    label=f'"{kata}" is spoken English — transcribe as "{eng}"', fix=f'Write "{eng}".'))
        if has_en:
            for kata, eng in _KATA_EN_CHECK.items():
                if kata in ln.text:
                    out.append(Flag(rule="untranslated_english", severity="review", line=ln.n, evidence=kata,
                        label=f'"{kata}" may be spoken English "{eng}" (bilingual line) — verify',
                        fix=f'If spoken in English, write "{eng}".'))
    return out


def segments(text):
    """Split text into consecutive (lang, run) chunks at script boundaries. Punctuation
    and spaces attach to the surrounding run so runs stay readable."""
    out = []
    cur_lang, cur = None, ""
    for ch in text:
        if _JP.search(ch):
            l = "ja"
        elif _LATIN.search(ch):
            l = "en"
        else:
            l = None  # punctuation/space/digit -> stick with current run
        if l is None or l == cur_lang or cur_lang is None:
            cur += ch
            if l is not None:
                cur_lang = cur_lang or l
        else:
            out.append((cur_lang, cur))
            cur, cur_lang = ch, l
    if cur:
        out.append((cur_lang or "neutral", cur))
    # merge tiny neutral-only trailing bits handled implicitly; coalesce same-lang neighbours
    merged = []
    for lang, run in out:
        if merged and merged[-1][0] == lang:
            merged[-1] = (lang, merged[-1][1] + run)
        else:
            merged.append((lang, run))
    return merged
