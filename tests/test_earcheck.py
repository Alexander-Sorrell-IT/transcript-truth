"""earcheck — draft parsing (⚠ / **?Name:** / timestamp interpolation) and the
resolution round-trip. Interactive I/O (_getch/_read_replacement) and audio playback
(cut_and_play) are monkeypatched: no tty, no ffmpeg, no audio in tests."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import earcheck
from transcript_truth.earcheck import parse_draft


# Realistic multi-marker snippet in the T4791286 draft convention: header comments,
# bold speaker labels, ⚠ notes, **?Name:** unconfirmed speakers, a bold HH:MM:SS
# marker AND a plain MM:SS one. Line numbers matter to the tests below.
DRAFT = """\
# T000 00:00-06:00 — DRAFT (verify by ear before FINISH)
# ⚠ = engine-uncertain span, judge by ear.

**Staff:** よろしくお願いします。

**?Bose:** はい、分かりました。

**Bose:** テスト、テスト。 ⚠(英語表記はガイドライン次第)

**ANI:** どうも、ANIです。 **[00:02:00]**

**Staff:** カメラは気にせずで。

**?SHINCO:** そうですね。 ⚠

**Bose:** 一応ですね、企画って。 [04:00]

**Interviewer:** ありがとうございます。
"""


def entries():
    return parse_draft(DRAFT)


# --- parse_draft ---

def test_content_lines_only_headers_and_blanks_skipped():
    lines = [e["line_no"] for e in entries()]
    assert lines == [4, 6, 8, 10, 12, 14, 16, 18]   # ordered, no #-comments, no blanks


def test_flagged_detects_warning_mark_and_unsure_speaker():
    by_line = {e["line_no"]: e for e in entries()}
    assert by_line[6]["flagged"]           # **?Bose:** — unconfirmed speaker
    assert by_line[8]["flagged"]           # ⚠ note
    assert by_line[14]["flagged"]          # both at once
    assert not by_line[4]["flagged"]       # confirmed speaker, no mark
    assert not by_line[10]["flagged"]      # timestamp marker is not a flag


def test_timestamps_anchor_bold_hms_and_plain_ms():
    by_line = {e["line_no"]: e for e in entries()}
    assert by_line[10]["approx_seconds"] == 120.0   # **[00:02:00]** bold HH:MM:SS
    assert by_line[16]["approx_seconds"] == 240.0   # [04:00] plain MM:SS


def test_interpolation_linear_between_anchors_and_monotonic():
    by_line = {e["line_no"]: e for e in entries()}
    assert by_line[4]["approx_seconds"] == 0.0      # implicit 00:00 start anchor
    assert by_line[6]["approx_seconds"] == 40.0     # (6-4)/(10-4) * 120
    assert by_line[8]["approx_seconds"] == 80.0
    assert by_line[12]["approx_seconds"] == 160.0   # 120 + (12-10)/(16-10) * 120
    assert by_line[14]["approx_seconds"] == 200.0
    assert by_line[18]["approx_seconds"] == 280.0   # extrapolated at last-segment rate
    secs = [e["approx_seconds"] for e in entries()]
    assert secs == sorted(secs)                     # monotonic over the whole draft


def test_no_markers_all_zero_and_dialogue_parens_time_not_an_anchor():
    got = parse_draft("**A:** それは(1:02:30)頃でした。 ⚠\n\n**B:** はい。\n")
    assert [e["approx_seconds"] for e in got] == [0.0, 0.0]
    assert got[0]["flagged"] and not got[1]["flagged"]


# --- interactive loop: round-trip, resume-skip, replay ---

def scripted(monkeypatch, keys, replacements=(), plays=None):
    """Wire the loop to a key script + canned edits; record cut_and_play calls."""
    seq = iter(keys)
    monkeypatch.setattr(earcheck, "_getch", lambda: next(seq))
    reps = iter(replacements)
    monkeypatch.setattr(earcheck, "_read_replacement", lambda: next(reps))
    played = plays if plays is not None else []
    monkeypatch.setattr(earcheck, "cut_and_play",
                        lambda audio, center_s, **kw: played.append(center_s) or True)
    return played


def make_draft(tmp_path):
    p = tmp_path / "draft.md"
    p.write_text(DRAFT, encoding="utf-8")
    return str(p)


def test_round_trip_writes_ear_json(tmp_path, monkeypatch, capsys):
    draft = make_draft(tmp_path)
    played = scripted(monkeypatch, keys=["k", "e", "u"], replacements=["直した行です。"])
    rc = earcheck.run(draft, "audio.mp3")
    assert rc == 0
    assert played == [40.0, 80.0, 200.0]            # one clip per flagged span
    data = json.loads(open(draft + ".ear.json", encoding="utf-8").read())
    assert data["total_flagged"] == 3
    assert data["resolved"] == [
        {"line_no": 6, "decision": "keep", "replacement": None},
        {"line_no": 8, "decision": "edit", "replacement": "直した行です。"},
        {"line_no": 14, "decision": "unresolved", "replacement": None},
    ]


def test_quit_saves_partial_and_resume_skips_decided(tmp_path, monkeypatch):
    draft = make_draft(tmp_path)
    # Session 1: keep line 6, then quit at line 8 — partial progress must survive.
    scripted(monkeypatch, keys=["k", "q"])
    earcheck.run(draft, "audio.mp3")
    data = json.loads(open(draft + ".ear.json", encoding="utf-8").read())
    assert data["resolved"] == [{"line_no": 6, "decision": "keep", "replacement": None}]
    # Session 2: line 6 skipped — only lines 8 and 14 play and get asked.
    played = scripted(monkeypatch, keys=["k", "k"])
    earcheck.run(draft, "audio.mp3")
    assert played == [80.0, 200.0]
    data = json.loads(open(draft + ".ear.json", encoding="utf-8").read())
    assert [r["line_no"] for r in data["resolved"]] == [6, 8, 14]
    assert all(r["decision"] == "keep" for r in data["resolved"])


def test_unresolved_requeues_and_is_replaced_not_duplicated(tmp_path, monkeypatch):
    draft = make_draft(tmp_path)
    scripted(monkeypatch, keys=["k", "k", "u"])     # line 14 punted
    earcheck.run(draft, "audio.mp3")
    # Resume: keep/edit are done, but the unresolved line re-queues by design.
    played = scripted(monkeypatch, keys=["e"], replacements=["こちらが正です。"])
    earcheck.run(draft, "audio.mp3")
    assert played == [200.0]
    data = json.loads(open(draft + ".ear.json", encoding="utf-8").read())
    assert len(data["resolved"]) == 3               # replaced in place, no duplicate
    assert data["resolved"][-1] == \
        {"line_no": 14, "decision": "edit", "replacement": "こちらが正です。"}


def test_replay_and_unknown_key_reprompt(tmp_path, monkeypatch):
    draft = make_draft(tmp_path)
    # span 1: replay once then keep; span 2: junk key re-prompts (no re-play), keep;
    # span 3: keep. Total plays = 3 spans + 1 replay.
    played = scripted(monkeypatch, keys=["r", "k", "x", "k", "k"])
    rc = earcheck.run(draft, "audio.mp3")
    assert rc == 0
    assert played == [40.0, 40.0, 80.0, 200.0]


def test_all_resolved_second_run_asks_nothing(tmp_path, monkeypatch, capsys):
    draft = make_draft(tmp_path)
    scripted(monkeypatch, keys=["k", "k", "k"])
    earcheck.run(draft, "audio.mp3")
    played = scripted(monkeypatch, keys=[])         # any keypress would StopIteration
    rc = earcheck.run(draft, "audio.mp3")
    assert rc == 0 and played == []
    assert "all resolved" in capsys.readouterr().out


def test_corrupt_resolution_file_starts_fresh_not_traceback(tmp_path, monkeypatch):
    draft = make_draft(tmp_path)
    open(draft + ".ear.json", "w").write("{half-written garbag")   # 3AM crash artifact
    played = scripted(monkeypatch, keys=["k", "k", "k"])
    assert earcheck.run(draft, "audio.mp3") == 0
    assert len(played) == 3


def test_no_flagged_spans_is_a_clean_exit(tmp_path, monkeypatch, capsys):
    p = tmp_path / "clean.md"
    p.write_text("**A:** 完全に確定した行。\n", encoding="utf-8")
    assert earcheck.run(str(p), "audio.mp3") == 0
    assert "nothing to ear-check" in capsys.readouterr().out
    assert not os.path.exists(str(p) + ".ear.json")   # no verdicts -> no file
