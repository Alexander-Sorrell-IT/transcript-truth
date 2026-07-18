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
    if latin_source:
        # Latin source: reliable capitalized-gazetteer extraction, exact diacritic-folded survival.
        src_names = _latin_names(source_text, src_lang)
        missing_names = sorted(n for n in src_names if not _name_survives(n, translation))
        names_verifiable = True
    else:
        # Non-Latin source (ar/hi/ur/ja): romanize source names and fuzzy-match by consonant
        # skeleton (translit.name_survival_translit owns the never-fake-pass gate). names_verifiable
        # is True ONLY when a faithful romanizer + trustworthy identifier exist for the language;
        # otherwise it stays False and src_names is empty (no drift to passed/total).
        from .translit import name_survival_translit
        _tr = name_survival_translit(source_text, translation, src_lang, tgt_lang)
        src_names = set(_tr["checked"])
        missing_names = _tr["missing_names"]
        names_verifiable = _tr["verifiable"]

    total = sum(src_nums.values()) + len(src_names)
    passed = total - len(missing_nums) - len(missing_names)
    return {"ok": not missing_nums and not introduced and not missing_names,
            "numbers_verifiable": nums_verifiable, "names_verifiable": names_verifiable,
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


def _build_review(checks: dict | None, agree: float, have_both: bool) -> list[dict]:
    """SURFACE-FOR-REVIEW (Phase 8 task 5): a structured, human-readable list of the SPECIFIC
    reasons a bilingual reviewer should look at this clip. This is NOT the verdict path — it only
    explains what the deterministic checks found or could not check; semantic faithfulness never
    enters here. Each item: {check, severity (critical|moderate|minor|review), evidence, detail}."""
    review: list[dict] = []
    if checks is None:
        review.append({"check": "no_output", "severity": "critical", "evidence": "",
                       "detail": "no witness produced a translation — nothing to verify"})
        return review
    for n in checks.get("missing_numbers", []):
        review.append({"check": "missing_number", "severity": "critical", "evidence": str(n),
                       "detail": f"number {n} in the source is absent from the translation"})
    for n in checks.get("introduced_numbers", []):
        review.append({"check": "introduced_number", "severity": "critical", "evidence": str(n),
                       "detail": f"number {n} appears in the translation but not the source"})
    for nm in checks.get("missing_names", []):
        review.append({"check": "missing_name", "severity": "moderate", "evidence": str(nm),
                       "detail": f"proper name {nm!r} did not survive into the translation"})
    if checks.get("numbers_verifiable") is False:
        review.append({"check": "numbers_unverifiable", "severity": "review", "evidence": "",
                       "detail": "spelled-number support missing for this language pair — number "
                                 "survival could not be mechanically checked"})
    if checks.get("names_verifiable") is False:
        review.append({"check": "names_unverifiable", "severity": "review", "evidence": "",
                       "detail": "no reliable transliterator/identifier for this non-Latin source "
                                 "— name survival could not be mechanically checked"})
    if have_both and agree < _AGREE_FLOOR:
        review.append({"check": "low_agreement", "severity": "moderate", "evidence": str(agree),
                       "detail": f"the two independent witnesses agree only {agree} (< {_AGREE_FLOOR})"})
    if not have_both:
        review.append({"check": "lone_witness", "severity": "review", "evidence": "",
                       "detail": "only one witness produced output — no cross-witness control"})
    return review


# run_qa flag kinds that are CONFIDENT positives — a real, mechanically-detected defect in the
# primary translation. These drive the headline `flagged` verdict, not just the review surface.
_QA_HARD_KINDS = {"source_script_leak", "untranslated_passthrough", "glossary", "length_ratio"}
_QA_SEVERITY = {"source_script_leak": "critical", "untranslated_passthrough": "critical",
                "glossary": "moderate", "length_ratio": "review"}


def _run_qa_safe(source_text: str, translation: str, src_lang: str, tgt_lang: str):
    """GUARDED optional call to the parallel translation_qa.run_qa module (builder B). Its absence
    or failure must NEVER break translate() — returns None then. Otherwise the run_qa dict."""
    try:
        from .translation_qa import run_qa
    except Exception:
        return None
    try:
        return run_qa(source_text, translation, src_lang, tgt_lang)
    except Exception:
        return None


def _qa_has_hard_flag(qa) -> bool:
    """True when run_qa found a confident defect in the PRIMARY translation (leak / untranslated
    passthrough / glossary miss / gross length anomaly) — this must flip the headline verdict, so
    the QA layer is a real control, not a decorative review line."""
    return bool(qa and any(f.get("kind") in _QA_HARD_KINDS for f in qa.get("flags", [])))


def _merge_qa_flags(review: list[dict], qa) -> None:
    """Fold an already-computed run_qa result into the review surface (dedup on check+evidence).
    run_qa emits {kind, evidence, note}; map onto the review shape {check, severity, evidence, detail}."""
    if not qa:
        return
    seen = {(r.get("check"), r.get("evidence")) for r in review}
    for fl in qa.get("flags", []):
        kind = fl.get("kind", "qa")
        key = (kind, fl.get("evidence"))
        if key in seen:
            continue
        seen.add(key)
        review.append({"check": kind, "severity": _QA_SEVERITY.get(kind, "review"),
                       "evidence": fl.get("evidence", ""), "detail": fl.get("note", "")})


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
                "checks": None, "checks_alt": None, "review": _build_review(None, 0.0, False),
                "transcript": transcript, "src_lang": src_lang, "tgt_lang": tgt_lang}

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

    # translation-QA on the PRIMARY (source-script leak, untranslated passthrough, glossary,
    # length anomaly). A confident QA defect is its OWN control — it drives the headline verdict,
    # not just the review surface (else an es->en verbatim passthrough, where numbers/names
    # trivially "survive" and the witnesses agree, would ship a silent green).
    qa = _run_qa_safe(transcript, primary, src_lang, tgt_lang)
    qa_flagged = _qa_has_hard_flag(qa)

    flagged = (not checks["ok"]) or (have_both and agree < _AGREE_FLOOR) \
        or not have_both or (not checkable and not have_both) or qa_flagged

    # SURFACE-FOR-REVIEW: structured reasons a bilingual reviewer should check (additive to the
    # verdict). Fold in the already-computed run_qa flags (guarded — module absence never breaks).
    review = _build_review(checks, agree, have_both)
    _merge_qa_flags(review, qa)
    return {"text": primary, "alt": alt, "agreement": agree, "flagged": flagged,
            "checks": checks, "checks_alt": checks_alt, "review": review,
            "transcript": transcript, "src_lang": src_lang, "tgt_lang": tgt_lang}
