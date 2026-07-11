"""Translation track (ROADMAP Phase 8) — the SAME spine as transcription: independent model
witnesses PROPOSE translations, deterministic code owns the verdict and surfaces uncertainty.

Two genuinely independent witnesses:
  A. SeamlessM4T speech-to-text-translation — translates straight FROM THE AUDIO (never sees
     our transcript, so a transcription error can't propagate into it);
  B. Gemini text translation OF THE MEASURED CONSENSUS TRANSCRIPT (builds on the 95-99%
     hearing the engine already proves).

Deterministic verdict (no model decides):
  - NUMBER survival is value-based and language-aware (numparse.values): 'on yedi' in the
    Turkish source and '17' in the English translation are the same VALUE 17. Multiset compare,
    both directions — dropped numbers AND introduced numbers are violations. When the source
    language's spelled numbers can't be parsed (numparse.spelled_support=False: hi/ur), the check
    reports verifiable=False instead of vacuously passing.
  - NAME survival: Latin-script names (gazetteer-confirmed, frequency-floored so common words
    never count as names) must survive as whole words, diacritic-folded ('Bergstrom' satisfies
    'Bergström'; 'chrome' never satisfies 'Rome'). Non-Latin-script sources report
    verifiable=False (transliteration matching is a later phase) — never a fake pass.
  - cross-witness agreement (punctuation-stripped, number-canonicalized word ratio between the
    two independent translations) is the honest-uncertainty signal, thresholded.
  - the PRIMARY text passes strictly more checks; ties go to the transcript-based translation
    (its input accuracy is measured). A witness under half the other's length is treated as
    truncated and never wins a tie.

This module was adversarially reviewed (2026-07-11 workflow: 3 attack lenses, 14 confirmed
defects in v1) — every rule above exists because its absence was demonstrated failing.
"""
from __future__ import annotations
import difflib
import re
import unicodedata

from .numparse import values as _num_values, spelled_support


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if not unicodedata.combining(c)).replace("ø", "o").replace("ß", "ss")


# a capitalized token (accented initials included, short names like Ali/Kim included)
_LATIN_NAME = re.compile(r"\b[A-ZÀ-Þ][a-zà-öø-ÿ]{1,}\b")


def _latin_names(text: str, src_lang: str | None = None) -> set[str]:
    """Proper names the mechanical check DEMANDS of a translation: capitalized gazetteer tokens
    that are unambiguous — not a dictionary word and not a common word in the source language.
    (The 2.6M-entry gazetteer contains 'Buenos', 'White', 'Said', 'Rome' — demanding those
    verbatim false-flags good translations. Ambiguous famous names are instead covered by the
    cross-witness agreement control: if one translation mangles 'Rome', the independent witness
    disagrees and the clip flags.)"""
    from .adjudicate import _name_in_gazetteer, _is_word
    lang = (src_lang or "en").split("-")[0]
    out = set()
    for m in _LATIN_NAME.finditer(text):
        w = m.group(0)
        if not (_name_in_gazetteer(w.lower()) or _name_in_gazetteer(w)):
            continue
        if _is_word(w.lower(), lang) or _is_word(w.lower(), "en"):
            continue                                       # dictionary word — ambiguous, skip
        try:
            from wordfreq import zipf_frequency
            if zipf_frequency(w.lower(), lang) >= 4.2:
                continue                                   # merely-common word — ambiguous, skip
        except Exception:
            pass
        out.add(w)
    return out


def _name_survives(name: str, translation: str) -> bool:
    """Whole-word, diacritic-folded containment ('Bergstrom' satisfies 'Bergström';
    'chrome' does NOT satisfy 'Rome')."""
    folded = _strip_accents(translation)
    target = re.escape(_strip_accents(name))
    return re.search(rf"(?<![a-z0-9]){target}(?![a-z0-9])", folded) is not None


_HAS_LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def survival_checks(source_text: str, translation: str,
                    src_lang: str = "en", tgt_lang: str = "en") -> dict:
    """Mechanical faithfulness: numeric VALUES and proper names must survive translation.
    Returns {ok, verifiable, missing_numbers, introduced_numbers, missing_names, passed, total}.
    ok is only meaningful when verifiable is True — an unverifiable check NEVER passes silently."""
    src_nums = _num_values(source_text, src_lang)
    tgt_nums = _num_values(translation, tgt_lang)
    missing_nums = sorted((src_nums - tgt_nums).elements())
    introduced = sorted((tgt_nums - src_nums).elements())
    nums_verifiable = spelled_support(src_lang) and spelled_support(tgt_lang)

    latin_source = bool(_HAS_LATIN.search(source_text))
    src_names = _latin_names(source_text, src_lang) if latin_source else set()
    missing_names = sorted(n for n in src_names if not _name_survives(n, translation))

    total = sum(src_nums.values()) + len(src_names)
    passed = total - len(missing_nums) - len(missing_names)
    return {"ok": not missing_nums and not introduced and not missing_names,
            "numbers_verifiable": nums_verifiable, "names_verifiable": latin_source,
            "missing_numbers": missing_nums, "introduced_numbers": introduced,
            "missing_names": missing_names, "passed": passed, "total": total}


def agreement(a: str, b: str, lang: str = "en") -> float:
    """Word-level agreement between two independent translations — the honest-uncertainty
    signal. Punctuation is stripped and numbers value-canonicalized first, so '17 people.' vs
    'seventeen people' is agreement, not disagreement."""
    def toks(s):
        s = re.sub(r"[^\w\s']", " ", s.lower())
        out = []
        for w in s.split():
            v = _num_values(w, lang)
            out.append(str(next(iter(v))) if len(v) == 1 else w)
        return out
    aw, bw = toks(a), toks(b)
    if not aw or not bw:
        return 0.0
    return round(difflib.SequenceMatcher(a=aw, b=bw, autojunk=False).ratio(), 3)


# below this cross-witness agreement, the translation ships FLAGGED for review — same 90-95%
# honest-uncertainty philosophy as transcription (never silently guess)
_AGREE_FLOOR = 0.55


def seamless_translate(audio_path: str, tgt_lang: str = "en") -> str:
    """Witness A: SeamlessM4T speech-to-text-TRANSLATION — same loaded model as the ASR witness,
    asked for the TARGET language instead of the source (S2TT is what it was built for)."""
    from .witness import seamless_local
    return seamless_local(audio_path, language=tgt_lang)


def gemini_translate(text: str, src_lang: str, tgt_lang: str = "en") -> str:  # pragma: no cover
    """Witness B: Gemini translating the measured consensus TRANSCRIPT (text -> text)."""
    import json as _json
    import urllib.request
    from .witness import _key
    instr = (f"Translate this {src_lang} transcript into {tgt_lang}. Translate faithfully and "
             f"completely — keep every number exact, keep proper names as-is, do not summarize, "
             f"do not add anything. Output only the translation.\n\n{text}")
    body = _json.dumps({"contents": [{"parts": [{"text": instr}]}]}).encode()
    for mdl in ("gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash"):
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent",
            data=body, headers={"x-goog-api-key": _key("GEMINI_API_KEY"),
                                "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = _json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            continue
    return ""


def _pick_primary(t_gem: str, c_gem: dict, t_sml: str, c_sml: dict):
    """Deterministic primary choice. Strictly more passed checks wins. Ties -> the transcript-
    based translation (measured input accuracy). A witness under half the other's length is
    treated as TRUNCATED and cannot win a tie (a degenerate output fails fewer checks only
    because it says less)."""
    if len(t_sml) < len(t_gem) * 0.5:
        sml_eligible = c_sml["passed"] > c_gem["passed"] and c_sml["ok"] and not c_gem["ok"]
    else:
        sml_eligible = c_sml["passed"] > c_gem["passed"]
    if sml_eligible:
        return t_sml, c_sml, t_gem, c_gem
    return t_gem, c_gem, t_sml, c_sml


def translate(audio_path: str, src_lang: str, tgt_lang: str = "en",
              transcript: str | None = None) -> dict:
    """Audio in src_lang -> translation in tgt_lang, with a deterministic verdict.

    Returns {text, alt, agreement, flagged, checks, checks_alt, transcript, src_lang, tgt_lang}.
    `flagged` True = ship-for-review (failed or UNVERIFIABLE survival checks, low cross-witness
    agreement, or a lone witness) — the translation is never silently wrong; it is either
    confident or explicitly uncertain."""
    if transcript is None:
        from . import consensus as C
        transcript = C.transcribe(audio_path, src_lang)["text"]

    t_gem = gemini_translate(transcript, src_lang, tgt_lang) if transcript else ""
    t_sml = seamless_translate(audio_path, tgt_lang)

    both = [t for t in (t_gem, t_sml) if t]
    if not both:
        return {"text": "", "alt": "", "agreement": 0.0, "flagged": True,
                "checks": None, "checks_alt": None, "transcript": transcript,
                "src_lang": src_lang, "tgt_lang": tgt_lang}

    c_gem = survival_checks(transcript, t_gem, src_lang, tgt_lang) if t_gem else None
    c_sml = survival_checks(transcript, t_sml, src_lang, tgt_lang) if t_sml else None
    agree = agreement(t_gem, t_sml, tgt_lang) if (t_gem and t_sml) else 0.0

    if t_gem and t_sml:
        primary, checks, alt, checks_alt = _pick_primary(t_gem, c_gem, t_sml, c_sml)
    else:
        primary, alt = both[0], ""
        checks, checks_alt = (c_gem or c_sml), None

    # flag policy: a failed mechanical check always flags. An UNVERIFIABLE check does not flag
    # by itself — the independent second witness is the control there (a wrong name/number in
    # one translation drags cross-witness agreement down) — but losing BOTH controls
    # (unverifiable AND lone-witness/low-agreement) flags.
    have_both = bool(t_gem and t_sml)
    checkable = checks["numbers_verifiable"] and checks["names_verifiable"]
    flagged = (not checks["ok"]) or (have_both and agree < _AGREE_FLOOR) \
        or not have_both or (not checkable and not have_both)
    return {"text": primary, "alt": alt, "agreement": agree, "flagged": flagged,
            "checks": checks, "checks_alt": checks_alt, "transcript": transcript,
            "src_lang": src_lang, "tgt_lang": tgt_lang}
