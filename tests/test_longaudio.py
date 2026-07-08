"""Long-audio + multi-model consensus tests (Phase 0). Pure/no-API — same discipline as the
rest of the suite. Covers chunk stitching, cross-chunk speaker reconciliation, the reference-map,
the measurement ruler, and cross-diarizer consensus."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import consensus as C, metrics as M
from transcript_truth import speaker_consensus as SC


# --- chunk read stitching (_splice) ---
def test_splice_dedups_overlap():
    a = "alpha bravo charlie delta echo foxtrot golf hotel"
    b = "echo foxtrot golf hotel india juliet kilo"           # shares a 4-word overlap
    merged, ok = C._splice(a, b, win=20)
    assert ok and merged.split().count("echo") == 1 and merged.endswith("kilo")


def test_splice_flags_when_no_overlap():
    merged, ok = C._splice("one two three four", "nine ten eleven twelve", win=20)
    assert ok is False                                          # no shared run -> flagged, not silent


# --- cross-chunk speaker reconciliation (_merge_diarized_chunks) ---
def test_merge_reconciles_permuted_speaker_ids():
    c0 = [{"start": 50, "end": 110, "speaker": "speaker_0", "text": "X"},
          {"start": 110, "end": 120, "speaker": "speaker_0", "text": "X"},
          {"start": 120, "end": 130, "speaker": "speaker_1", "text": "Y"}]
    c1 = [{"start": 110, "end": 120, "speaker": "speaker_1", "text": "X"},   # PERMUTED ids
          {"start": 120, "end": 130, "speaker": "speaker_0", "text": "Y"},
          {"start": 140, "end": 150, "speaker": "speaker_1", "text": "X"},
          {"start": 150, "end": 160, "speaker": "speaker_0", "text": "Y"}]
    merged = C._merge_diarized_chunks([(0, c0), (110, c1)], overlap_s=20)
    labels = {t["text"]: t["speaker"] for t in merged}
    assert labels["X"] != labels["Y"]                          # two distinct voices kept distinct
    assert len({t["speaker"] for t in merged}) == 2            # not over-counted across the seam


# --- reference-map (apply_reference_speakers) ---
def test_reference_map_relabels_by_timeline():
    ref = [{"start": 0, "end": 10, "speaker": "A"}, {"start": 10, "end": 20, "speaker": "B"}]
    turns = [{"start": 2, "end": 4, "speaker": "x"}, {"start": 12, "end": 14, "speaker": "y"}]
    out = SC.apply_reference_speakers(turns, ref)
    assert out[0]["speaker"] == "A" and out[1]["speaker"] == "B"


# --- measurement ruler (metrics) ---
def test_diar_agreement_identical_but_renamed_is_100():
    ref = [{"start": 0, "end": 10, "speaker": "A"}, {"start": 10, "end": 20, "speaker": "B"}]
    renamed = [{"start": 0, "end": 10, "speaker": "z"}, {"start": 10, "end": 20, "speaker": "q"}]
    assert M.diar_agreement(ref, renamed)["agreement_pct"] == 100.0


def test_diar_agreement_penalizes_wrong():
    ref = [{"start": 0, "end": 10, "speaker": "A"}, {"start": 10, "end": 20, "speaker": "B"}]
    wrong = [{"start": 0, "end": 20, "speaker": "A"}]            # collapses two speakers into one
    assert M.diar_agreement(ref, wrong)["agreement_pct"] < 80


def test_wer():
    assert M.wer("the cat sat", "the cat sat") == 0.0
    assert M.wer("the quick brown fox", "the quick brown dog") == 0.25


def test_wer_number_aware_ignores_formatting():
    # "15%" vs "fifteen percent" is formatting, not an error
    assert M.wer("revenue rose fifteen percent", "revenue rose 15%") == 0.0
    assert M.wer("she turned twenty-one", "she turned 21") == 0.0          # cardinal, not a year guess
    assert M.wer("forty seven million dollars", "47 million dollars") == 0.0
    assert M.wer("take 5-10 mg", "take 5-10 mg") == 0.0                     # ranges left intact, not summed
    # but a real word error is still counted
    assert M.wer("doctor eleanor vance", "doctor elena vance", normalize_numbers=True) > 0
    # raw mode still sees formatting as a diff
    assert M.wer("fifteen percent", "15%", normalize_numbers=False) > 0


# --- cross-diarizer consensus ---
def test_cross_consensus_flags_disagreement():
    d1 = [{"start": 0, "end": 10, "speaker": "A", "text": "hi"},
          {"start": 10, "end": 20, "speaker": "B", "text": "yo"}]
    d2 = [{"start": 0, "end": 10, "speaker": "p", "text": "hi"},   # agrees on turn 1 (p->A)
          {"start": 10, "end": 20, "speaker": "p", "text": "yo"}]  # disagrees on turn 2
    rep = SC.cross_consensus({"d1": d1, "d2": d2}, 0, 20)
    assert rep["n_diarizers"] == 2 and rep["agreement_pct"] is not None
    assert len(rep["review_turns"]) >= 1                        # the disagreement is surfaced


def test_cross_consensus_single_diarizer_no_consensus():
    only = [{"start": 0, "end": 10, "speaker": "A", "text": "hi"}]
    rep = SC.cross_consensus({"d1": only}, 0, 10)
    assert rep["agreement_pct"] is None and rep["n_diarizers"] == 1


# --- Phase 3: French profile (pure, no API) ---
def test_french_profile_registered_and_routes():
    from transcript_truth.profiles import REGISTRY
    from transcript_truth import language as L
    assert "fr" in REGISTRY and "fr:full" in REGISTRY
    assert L.profile_for("fr") == "fr"


def test_french_spacing_rule():
    from transcript_truth import audit_transcript
    flags = audit_transcript("Vraiment? Oui «oui» bien.", profile="fr").flags
    sp = [f for f in flags if f.rule == "fr_spacing"]
    assert any("?" in f.evidence for f in sp)              # space required before ?
    assert any("«" in f.evidence or "»" in f.evidence for f in sp)  # guillemets


def test_french_spacing_ignores_times():
    from transcript_truth import audit_transcript
    flags = audit_transcript("Il est 12:30 maintenant.", profile="fr").flags
    assert not any(f.rule == "fr_spacing" for f in flags)  # 12:30 is a time, not a typo


# --- Phase 3: German / Portuguese / Turkish profiles (pure, no API) ---
def test_tier1_profiles_registered():
    from transcript_truth.profiles import REGISTRY
    for p in ("de", "pt", "tr", "de:full", "pt:full", "tr:full"):
        assert p in REGISTRY, p


def test_german_old_spelling():
    from transcript_truth import audit_transcript
    f = audit_transcript("Ich muß das daß sehen.", profile="de").flags
    ev = {x.evidence.lower() for x in f if x.rule == "de_old_spelling"}
    assert "muß" in ev and "daß" in ev


def test_portuguese_cedilla():
    from transcript_truth import audit_transcript
    assert any(x.rule == "pt_cedilla" for x in audit_transcript("um açidente", profile="pt").flags)
    assert not any(x.rule == "pt_cedilla" for x in audit_transcript("a praça", profile="pt").flags)  # ç+a ok


def test_turkish_foreign_letters():
    from transcript_truth import audit_transcript
    ev = {x.evidence for x in audit_transcript("wagon ve quiz", profile="tr").flags if x.rule == "tr_foreign_letter"}
    assert "wagon" in ev and "quiz" in ev


def test_all_tier1_languages_route_and_have_roster():
    from transcript_truth import language as L
    from transcript_truth.consensus import ROSTER
    for lang in ("fr", "de", "pt", "tr"):
        assert L.profile_for(lang) == lang and ROSTER.get(lang), lang


# --- Phase 4: Korean batchim particles (needs kiwipiepy; skip cleanly if absent) ---
def _kiwi_available():
    try:
        import kiwipiepy  # noqa
        return True
    except Exception:
        return False


def test_korean_profile_registered_and_routes():
    from transcript_truth.profiles import REGISTRY
    from transcript_truth import language as L
    from transcript_truth.consensus import ROSTER
    assert "ko" in REGISTRY and L.profile_for("ko") == "ko" and ROSTER.get("ko")


def test_korean_batchim_flags_wrong_particle():
    if not _kiwi_available():
        return
    from transcript_truth import audit_transcript
    f = audit_transcript("밥를 먹었어요.", profile="ko").flags   # 밥(batchim)+를 -> should be 을
    assert any(x.rule == "ko_particle" and x.evidence == "밥를" for x in f)


def test_korean_batchim_no_false_positive_on_real_words():
    if not _kiwi_available():
        return
    from transcript_truth import audit_transcript
    for w in ("마을이 좋다.", "차이가 있다.", "사과를 먹다.", "회의를 했다."):
        assert not any(x.rule == "ko_particle" for x in audit_transcript(w, profile="ko").flags), w


# --- Phase 4: Vietnamese (pure, no API) ---
def test_vietnamese_profile_and_foreign_letters():
    from transcript_truth import audit_transcript
    from transcript_truth.profiles import REGISTRY
    from transcript_truth.consensus import ROSTER
    from transcript_truth import language as L
    assert "vi" in REGISTRY and L.profile_for("vi") == "vi" and ROSTER.get("vi")
    ev = {f.evidence for f in audit_transcript("Tôi dùng wifi và jazz.", profile="vi").flags
          if f.rule == "vi_foreign_letter"}
    assert "wifi" in ev and "jazz" in ev
    # clean Vietnamese (no f/j/w/z) must not fire the foreign-letter rule
    assert not any(f.rule == "vi_foreign_letter"
                   for f in audit_transcript("Tôi thích cà phê Việt Nam.", profile="vi").flags)


# --- pyannote diarizer wiring (skips cleanly if pyannote/token absent) ---
def test_pyannote_registered_in_diarizers():
    # the diarizer name resolves in diarize_long's map without error path for unknown
    import transcript_truth.consensus as C
    import inspect
    src = inspect.getsource(C.diarize_long)
    assert '"pyannote"' in src and "pyannote_diarize" in src


# --- Phase 5: Arabic / Hindi / Urdu (pure, no API) ---
def test_tier3_profiles_registered():
    from transcript_truth.profiles import REGISTRY
    from transcript_truth.consensus import ROSTER
    for p in ("ar", "hi", "ur"):
        assert p in REGISTRY and ROSTER.get(p), p


def test_arabic_tatweel_and_latin_leak():
    from transcript_truth import audit_transcript
    assert any(f.rule == "tatweel" for f in audit_transcript("مرحباـ", profile="ar").flags)
    leak = audit_transcript("هذا هو الكمبيوتر laptop الجديد", profile="ar").flags
    assert any(f.rule == "latin_leak" and f.evidence == "laptop" for f in leak)


# --- Domain axis: medical composes with any language (pure, no API) ---
def test_domain_axis_registered():
    from transcript_truth.domains import domain_names, compose
    assert "medical" in domain_names()
    assert compose("en", "medical").name == "en+medical"
    assert compose("en", "general").name == "en"          # general = no extra rules


def test_medical_dangerous_abbreviations():
    from transcript_truth import audit_transcript
    f = audit_transcript("MS 1.0 mg QD; insulin 10 U.", profile="en", domain="medical").flags
    rules = {x.evidence for x in f if x.rule == "med_dangerous_abbrev"}
    assert "MS" in rules and "QD" in rules and "U" in rules
    assert any(x.rule == "med_dosage" for x in f)          # 1.0 mg trailing zero


def test_transcribeme_legal_rules():
    from transcript_truth import audit_transcript
    f = audit_transcript("He [laughs] said see Page 5.", profile="en", domain="legal", site="transcribeme").flags
    assert any(x.rule == "tm_sound_tag" and x.evidence == "[laughs]" for x in f)  # only coughs/sneezes/phone rings
    assert any(x.rule == "tm_lowercase" and x.evidence == "Page" for x in f)       # Bates terms lowercase
    # allowed sound tags + sentence-initial caps must stay clean
    ok = audit_transcript("The witness [coughs]. Page 5 shows it.", profile="en", domain="legal", site="transcribeme").flags
    assert not any(x.rule in ("tm_sound_tag", "tm_lowercase") for x in ok)


def test_transcribeme_legal_structure():
    from transcript_truth import audit_transcript
    f = audit_transcript("Mr. Smith   I was going-- I mean, I was -- there.", profile="en", domain="legal", site="transcribeme").flags
    assert any(x.rule == "tm_speaker_caps" and x.evidence == "Mr. Smith" for x in f)  # Colloquy ID caps
    assert any(x.rule == "tm_double_dash" for x in f)                                  # dash attaches
    ok = audit_transcript("MR. SMITH   I was going-- I mean, there.", profile="en", domain="legal", site="transcribeme").flags
    assert not any(x.rule in ("tm_speaker_caps", "tm_double_dash") for x in ok)


def test_transcribeme_spoken_punctuation():
    from transcript_truth import audit_transcript
    f = audit_transcript("Runny nose, comma, sore throat, comma, and red eyes, stop.", profile="legal").flags
    assert sum(1 for x in f if x.rule == "tm_spoken_punct") == 3   # two commas + one stop
    # real nouns "comma"/"period" must NOT flag
    ok = audit_transcript("That line needs a comma. She had a rough period.", profile="legal").flags
    assert not any(x.rule == "tm_spoken_punct" for x in ok)


def test_medical_drug_name_check():
    from transcript_truth.medical_data import drug_set
    if not drug_set():
        return                                             # drug list not downloaded (--refresh-data); skip
    from transcript_truth import audit_transcript
    f = audit_transcript("gave metformine 500 mg", profile="en", domain="medical").flags
    assert any(x.rule == "med_drug_name" and x.evidence == "metformine" for x in f)
    # a real drug and a common verb in dose position must NOT flag
    assert not any(x.rule == "med_drug_name" for x in audit_transcript("took metformin 500 mg", profile="en", domain="medical").flags)
    assert not any(x.rule == "med_drug_name" for x in audit_transcript("gave 500 mg", profile="en", domain="medical").flags)


def test_legal_domain_core_plus_english_layer():
    from transcript_truth import audit_transcript
    from transcript_truth.domains import domain_names, domain_languages
    assert "legal" in domain_names() and domain_languages("legal") == ["en"]   # only en has the CVL layer
    # English gets the full CVL layer (English tag words, number rules, etc.)
    viol = "There were (laughs) twenty people and it was (inaudible)."
    en_rules = {f.rule for f in audit_transcript(viol, profile="en", domain="legal").flags}
    assert "legal_tag" in en_rules and "legal_number" in en_rules
    # non-English composes fine (universal core only) — the English CVL rules NEVER misfire on it
    for lang in ("fr", "ja", "ko"):
        assert not any(f.rule.startswith(("legal_", "tm_speaker", "tm_lowercase", "tm_spoken", "tm_sound"))
                       for f in audit_transcript("Bonjour, ceci est un test normal.", profile=lang, domain="legal").flags), lang
    # legal terminology (English layer): misspelled terms flagged, no false positives
    terms = audit_transcript("The subpena and the defendent.", profile="en", domain="legal").flags
    assert any(f.rule == "legal_term" and f.evidence == "subpena" for f in terms)
    assert not any(f.rule == "legal_term" for f in audit_transcript("The subpoena and the defendant.", profile="en", domain="legal").flags)


def test_umls_context_gating_multilingual():
    # offline, deterministic: the UMLS check is LANGUAGE-AWARE — each language contributes its own
    # diagnosis-context phrases; the same multilingual UMLS verifier runs for all. Only a term in a
    # clear diagnosis context is considered (never blanket-flags), and the API step is graceful.
    from transcript_truth.umls import _dx_regex
    en = _dx_regex("en")
    assert en.search("Patient diagnosed with pneumonia.").group(1).lower() == "pneumonia"
    assert en.search("History of hypertension today").group(1).lower() == "hypertension"
    assert en.search("She likes pneumonia trivia") is None            # no diagnosis context → no candidate
    # built once → other languages work via their own phrase rows; a language with none no-ops
    assert _dx_regex("es").search("diagnosticado con neumonía") is not None
    assert _dx_regex("fr").search("antécédents de diabète") is not None
    # verb-final languages capture the TERM BEFORE the trigger (ko/ja/hi/ur/tr)
    m = _dx_regex("ko").search("환자는 당뇨병 진단받았습니다.")
    assert m and m.group(1) == "당뇨병"
    m = _dx_regex("ja").search("患者は糖尿病と診断されました。")
    assert m and m.group(1) == "糖尿病"
    assert _dx_regex("xx") is None                                    # unknown language → safe no-op


def test_umls_no_false_positive_on_common_words():
    # a non-medical phrase after a diagnosis trigger ("history of arriving unannounced") must NOT
    # flag: the head is a common word (zipf>=3.0) so it's skipped BEFORE any UMLS call. Offline —
    # the frequency gate short-circuits, so no network is touched. Grade must stay A (review caps B).
    from transcript_truth import audit_transcript
    r = audit_transcript("She has a long history of arriving unannounced", profile="en", domain="medical")
    assert not any(f.rule == "med_umls_term" for f in r.flags)
    assert r.grade == "A"


def test_medical_domain_core_plus_english_layer():
    from transcript_truth import audit_transcript
    from transcript_truth.domains import domain_languages
    assert domain_languages("medical") == ["en"]                    # only en has the RxNorm layer
    # universal core = dosage-number hygiene — works in ANY language:
    for lang in ("en", "fr", "ko"):
        assert any(x.rule == "med_dosage"
                   for x in audit_transcript("2.50 mg", profile=lang, domain="medical").flags), lang
    # ...and is locale-safe: a thousands-separator period ("1.000 mg" = 1000) is NOT read as a decimal:
    assert not any(x.rule == "med_dosage"
                   for x in audit_transcript("1.000 mg", profile="de", domain="medical").flags)
    # ISMP dangerous abbreviations are UNIVERSAL core (Latin medical shorthand is dangerous in every
    # language's chart): 'MTX' fires in German and Japanese exactly as in English…
    for lang, txt in (("en", "Give MS now"),
                      ("de", "Der Patient erhielt 2,5 mg MTX."),
                      ("ja", "患者はMTX 2.5 mgを投与された。")):
        assert any(x.rule == "med_dangerous_abbrev"
                   for x in audit_transcript(txt, profile=lang, domain="medical").flags), lang
    # …but SHORT abbreviations need dose context, so real native words never false-positive
    # ('u' = tumor in Vietnamese), while '10 U' still fires:
    assert not any(x.rule.startswith("med_dangerous") or x.rule == "med_drug_name"
                   for x in audit_transcript("khối u ác tính", profile="vi", domain="medical").flags)
    assert any(x.rule == "med_dangerous_abbrev"
               for x in audit_transcript("tiêm 10 U insulin", profile="vi", domain="medical").flags)


# --- Phase 2: language routing (pure, no API) ---
def test_profile_for_maps_languages():
    from transcript_truth import language as L
    assert L.profile_for("ja") == "default" and L.profile_for("en") == "en"
    assert L.profile_for("ko") == "ko" and L.profile_for("fr") == "fr"
    assert L.profile_for("en-US") == "en"                  # locale stripped
    assert L.profile_for("zz") == "default"                # unknown -> default


def test_script_of_classifies():
    from transcript_truth import language as L
    assert L.script_of("あ") == "ja" and L.script_of("a") == "en"
    assert L.script_of("가") == "ko" and L.script_of("д") == "cyr"
    assert L.script_of(" ") is None


def test_every_language_with_a_roster_has_a_profile():
    from transcript_truth import language as L
    from transcript_truth.consensus import ROSTER
    for lang in ROSTER:
        assert L.profile_for(lang) != "default" or lang == "ja", f"{lang} routes nowhere"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
