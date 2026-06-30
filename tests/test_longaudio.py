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


def test_medical_composes_across_languages_no_false_positive():
    from transcript_truth import audit_transcript
    # same medical rules fire on French...
    fr = audit_transcript("Donner MS 1.0 mg.", profile="fr", domain="medical").flags
    assert any(x.rule == "med_dangerous_abbrev" and x.evidence == "MS" for x in fr)
    # ...but accented French words don't trip the single-letter 'u' rule
    assert not any(x.rule == "med_dangerous_abbrev"
                   for x in audit_transcript("Le patient a reçu le traitement.", profile="fr", domain="medical").flags)


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
