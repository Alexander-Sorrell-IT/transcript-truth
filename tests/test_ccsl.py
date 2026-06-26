"""CCSL conformance tests — offline, no network, no video file. They lock the
frame-accurate timecode formatter (integer-frame arithmetic, round-trip) and the
deterministic scanners that encode the CCSL hard contract, and they assert the
severity discipline: the three objective timecode violations are `critical`, the
subjective mode-tag check stays `review` (weight 0, never moves the grade)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.ccsl_format import frame_to_tc, tc_to_frames, duration_tc, is_valid_tc
from transcript_truth.ccsl_rules import (
    ccsl_timecode, ccsl_inout_order, ccsl_speaker_case, ccsl_speaker_mode,
)
from transcript_truth import engine
from transcript_truth.types import Transcript, Line


def _t(text):
    return Transcript(lines=[Line(1, text)])


# ----------------------------------------------------------------- formatter
def test_frame_to_tc_carry_boundaries():
    assert frame_to_tc(0, 24) == "00:00:00:00"
    assert frame_to_tc(23, 24) == "00:00:00:23"
    assert frame_to_tc(24, 24) == "00:00:01:00"
    assert frame_to_tc(25, 24) == "00:00:01:01"
    assert frame_to_tc(24 * 3600 + 24 * 5 + 7, 24) == "01:00:05:07"   # >1h value


def test_tc_roundtrip():
    for f in (0, 23, 24, 25, 90061):
        assert tc_to_frames(frame_to_tc(f, 24), 24) == f


def test_duration():
    assert duration_tc("01:12:04:09", "01:12:07:18", 24) == \
        frame_to_tc(tc_to_frames("01:12:07:18", 24) - tc_to_frames("01:12:04:09", 24), 24)


def test_is_valid_tc():
    assert is_valid_tc("01:12:04:09")
    assert is_valid_tc("01:12:04;09")          # drop-frame form
    assert not is_valid_tc("01:12:04")          # three-part / seconds-rounded
    assert not is_valid_tc("1:12")              # wrong shape


# ----------------------------------------------------------------- scanners
def test_timecode_scanner_fires_on_rounded():
    flags = ccsl_timecode(_t("SHOT 1  01:12:04 -> 01:12:07  CU action"))
    assert flags and all(f.severity == "critical" for f in flags)
    assert all(f.rule == "ccsl_timecode" for f in flags)


def test_inout_order_fires():
    flags = ccsl_inout_order(_t("SHOT 1  01:12:07:18 -> 01:12:04:09  CU action"))
    assert flags and flags[0].rule == "ccsl_inout_order"
    assert all(f.severity == "critical" for f in flags)


def test_speaker_case_fires():
    assert ccsl_speaker_case(_t("MARIA:  Hello there.")) == []      # clean
    bad = ccsl_speaker_case(_t("Maria:  Hello there."))             # flags
    assert bad and bad[0].severity == "moderate"


def test_review_flags_stay_review():
    flags = ccsl_speaker_mode(_t("MARIA (XYZ):  off to the side."))
    assert flags and all(f.severity == "review" for f in flags)


def test_conformant_row_no_critical():
    # the false-positive direction: a fully-conformant CCSL row must yield no critical flag
    text = ("SHOT 1  01:12:04:09 -> 01:12:07:18  CU action\n"
            "INT. HOUSE - DAY\n"
            "MARIA:  Hello there.\n")
    flags = engine.run_scanners(engine.parse_transcript(text, "clean_verbatim"),
                                engine.get_profile("ccsl").scanners)
    assert not any(f.severity == "critical" for f in flags), [f.label for f in flags]


def test_profile_registered_and_audits_offline():
    from transcript_truth.profiles._base import get
    assert get("ccsl").name == "ccsl"
    r = engine.audit_transcript("Maria:  hi\n", profile="ccsl")   # no network
    assert r.__class__.__name__ == "Receipt"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
