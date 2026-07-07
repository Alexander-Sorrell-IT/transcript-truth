"""DT profile + completeness gate — the two fixes for the 'missing/incorrect dialogue' rejection."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.profiles._base import get
from transcript_truth import profiles  # noqa: F401 — triggers profile auto-import
from transcript_truth.types import Transcript, Line
from transcript_truth import coverage


def _t(txt):
    return Transcript(lines=[Line(n=i + 1, text=l) for i, l in enumerate(txt.splitlines())])


CLEAN = """INTERVIEW PROJECT
DIALOGUE WITH JOHN SMITH
FILE NAME: ABC123
July 7, 2026
TRANSCRIBED BY DAILY TRANSCRIPTION_AS



ABC123     [00:00:00]

JOHN:  So, um, I went to the store, you know, and it was closed.

Q:  What did you do then?

JOHN:  I went home. [laugh]

ABC123     [00:00:30]

JOHN:  Yeah, that was the whole day.

[end of file: ABC123]"""


def test_clean_dt_transcript_passes_clean():
    p = get("dt")
    flags = [f for fn in p.scanners for f in fn(_t(CLEAN))]
    assert flags == [] or all(f.severity == "review" for f in flags), [f.label for f in flags]


def test_dt_catches_format_errors():
    p = get("dt")
    bad = "Interview\nJohn: i went\n[giggles]\nI was going — wait."
    rules = {f.rule for fn in p.scanners for f in fn(_t(bad))}
    assert "dt_header" in rules
    assert "dt_eof" in rules
    assert "dt_speaker" in rules
    assert "dt_tag" in rules          # [giggles] -> [laugh]
    assert "legal_dash_form" in rules


def test_completeness_gate_flags_missing_dialogue(monkeypatch):
    monkeypatch.setattr(coverage, "speech_segments", lambda p: [(0.0, 5.0), (5.0, 10.0), (30.0, 38.0)])
    r = coverage.verify_coverage("x.wav", [{"start": 0.0, "end": 5.0}, {"start": 5.0, "end": 10.0}])
    assert r["uncovered"] == [(30.0, 38.0)]
    assert r["covered_pct"] < 100


def test_completeness_gate_clean_when_all_covered(monkeypatch):
    monkeypatch.setattr(coverage, "speech_segments", lambda p: [(0.0, 5.0), (5.0, 10.0)])
    r = coverage.verify_coverage("x.wav", [{"start": 0.0, "end": 10.0}])
    assert r["uncovered"] == []
    assert r["covered_pct"] == 100.0
