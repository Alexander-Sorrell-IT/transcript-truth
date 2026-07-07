"""Vendor SITE plugins (language x field x site): rev, scribie, dt, gotranscript, transcribeme."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.engine import audit_transcript
from transcript_truth.domains import site_names


def rules(text, **kw):
    return {f.rule for f in audit_transcript(text, **kw).flags}


def test_all_five_sites_registered():
    assert {"dt", "gotranscript", "rev", "scribie", "transcribeme"} <= set(site_names())


def test_rev_catches_rev_violations():
    r = rules("Speaker 1: I was gonna say [inaudible] but Mm-hmm.\nSpeaker 2: w-o-r-d he said--",
              profile="en", site="rev")
    assert {"rev_tag", "rev_affirmative", "rev_contraction", "rev_spelled", "rev_punct"} <= r


def test_rev_clean_text_passes():
    r = rules('Speaker 1: I was going to say [inaudible 00:10:05], but Mm-hmm (affirmative).',
              profile="en", site="rev")
    assert not ({"rev_tag", "rev_affirmative", "rev_contraction"} & r)


def test_scribie_catches_scribie_violations():
    r = rules("Interviewer: We met etc. [inaudible] there.", profile="en", site="scribie")
    assert {"scribie_speaker", "scribie_style", "scribie_tag"} <= r


def test_scribie_clean_text_passes():
    r = rules("Speaker 1: We met at the park, etcetera was implied. [laughter] ____",
              profile="en", site="scribie")
    assert not ({"scribie_speaker", "scribie_style", "scribie_tag"} & r)


def test_site_composes_with_language_and_domain():
    r = rules("Juan: fui a la tienda [giggles]", profile="es", site="dt")
    assert "dt_tag" in r and "dt_speaker" in r
    r2 = rules("MSO4 10.0 mg QD", profile="en", domain="medical", site="rev")
    assert "med_dangerous_abbrev" in r2 and "med_dosage" in r2


def test_conflicting_vendors_disagree_on_the_same_text():
    # '--' interruption: correct for DT/TranscribeMe, WRONG for Rev — the axis must flip the verdict
    text = "JOHN:  I was going to--"
    assert "rev_punct" in rules(text, profile="en", site="rev")
    assert "rev_punct" not in rules(text, profile="en", site="dt")


def test_allegis_catches_violations():
    r = rules("Q: Were you gonna stop?\nA: [crosstalk] It was .5 miles — at 00:10:05.",
              profile="en", site="allegis")
    assert {"al_qa", "al_contraction", "al_tag", "al_number", "al_dash", "al_timestamp"} <= r


def test_allegis_clean_passes():
    r = rules("Q  Were you going to stop?\nA  [inaudible] It was 0.5 miles -- I think.",
              profile="en", site="allegis")
    assert not ({"al_qa", "al_contraction", "al_tag", "al_number", "al_dash", "al_timestamp"} & r)


def test_quicktate_catches_violations():
    r = rules("Speaker 1: call b-o-b at [indiscernible] tonight ***", profile="en", site="quicktate")
    assert {"qt_speaker", "qt_spelled", "qt_unknown"} <= r


def test_quicktate_inaudible_is_valid_for_word_groups():
    # iDictate rule: [inaudible] for a GROUP of words is correct Quicktate style
    r = rules("Next Speaker: they were [inaudible] before the meeting.", profile="en", site="quicktate")
    assert "qt_unknown" not in r


def test_all_nine_sites_registered():
    assert {"allegis", "dt", "gotranscript", "quicktate", "rev",
            "scribie", "transcribeme", "typeitup", "ubiqus"} <= set(site_names())
