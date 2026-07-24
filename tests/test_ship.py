"""SHIP GATE (transcript_truth.ship) — the mechanical refusal T4791286 was missing.
Pure-function checks first, then the ./check --ship wrapper path via subprocess (exit 3,
blockers printed, and — the point — NO grade on an unshippable file).
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.ship import load_ear, ship_check, ship_check_file

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(REPO, "check")


def _kinds(r):
    return [b["kind"] for b in r["blockers"]]


# ---------------------------------------------------------------- ⚠ spans

def test_warn_char_blocks():
    r = ship_check("**Bose:** はい、テスト。 ⚠(擬音・要確認)")
    assert r["ok"] is False
    assert _kinds(r) == ["unverified_span"]
    b = r["blockers"][0]
    assert b["line"] == 1 and b["evidence"].startswith("⚠")


def test_warn_resolved_by_ear_passes():
    text = "**Bose:** テスト。 ⚠(要確認)\n**ANI:** どうも。 ⚠"
    # both accepted ledger shapes, k (kept) and e (edited) both count as resolved
    assert ship_check(text, {"1": "k", "2": "e"})["ok"] is True
    assert ship_check(text, [{"line": 1, "decision": "kept"},
                             {"line": 2, "decision": "edited"}])["ok"] is True


def test_warn_partial_or_garbage_resolution_still_blocks():
    text = "**Bose:** テスト。 ⚠\n**ANI:** どうも。 ⚠"
    r = ship_check(text, {"1": "k"})                      # line 2 never listened to
    assert r["ok"] is False and [b["line"] for b in r["blockers"]] == [2]
    # an unreadable/unknown decision must not unlock the gate
    assert ship_check(text, {"1": "x", "2": "k"})["ok"] is False
    assert ship_check(text, {"one": "k", "2": "k"})["ok"] is False


# ---------------------------------------------------------------- ?speaker labels

def test_bold_unconfirmed_speaker_blocks():
    r = ship_check("**?Bose:** はい、分かりました。")
    assert r["ok"] is False and _kinds(r) == ["unconfirmed_speaker"]
    assert r["blockers"][0]["evidence"] == "**?Bose:**"


def test_plain_unconfirmed_speaker_blocks():
    r = ship_check("?Interviewer: なるほど。")
    assert r["ok"] is False and _kinds(r) == ["unconfirmed_speaker"]


def test_japanese_question_marks_never_block():
    # the false-positive constraint that matters most: JA text is full of "?"/"？"
    text = "\n".join([
        "**Bose:** はい、テスト。いかがでしょう？",            # full-width, sentence-final
        "**Staff:** iPhoneだったら大丈夫ですか?",              # ASCII, sentence-final
        "**ANI:** え? 本当? それで大丈夫?",                    # ASCII, mid-line, several
        "**SHINCO:** 「どうする？」と聞かれて。",              # quoted question
        "？と思ったんですけど。",                               # full-width at line START
    ])
    assert ship_check(text) == {"ok": True, "blockers": []}


def test_confirmed_speaker_labels_pass():
    assert ship_check("**Bose:** はい。\nStaff: どうぞ。")["ok"] is True


def test_speaker_not_ear_clearable():
    # confirming a speaker = editing the label; the ledger cannot clear it
    assert ship_check("**?Bose:** はい。", {"1": "k"})["ok"] is False


# ---------------------------------------------------------------- ear "u" + headers

def test_unresolved_ear_entry_blocks():
    r = ship_check("**Bose:** テスト。 ⚠", {"1": "u"})
    assert r["ok"] is False
    assert set(_kinds(r)) == {"unverified_span", "unresolved_ear"}     # honest "couldn't tell"
    # a "u" entry blocks even when the line itself carries no marker anymore
    r2 = ship_check("**Bose:** テスト。", {"1": "u"})
    assert r2["ok"] is False and _kinds(r2) == ["unresolved_ear"]


def test_draft_header_blocks_but_plain_header_does_not():
    r = ship_check("# T4791286 00:00–10:00 — DRAFT (verify by ear before FINISH)\n**Bose:** はい。")
    assert r["ok"] is False and _kinds(r) == ["draft_header"] and r["blockers"][0]["line"] == 1
    assert ship_check("# Verify the timestamp spec\n**Bose:** はい。")["ok"] is False
    assert ship_check("# episode notes\n**Bose:** はい。")["ok"] is True


def test_clean_text_passes():
    assert ship_check("**Bose:** はい、スチャダラパーのBoseです。\n\n**ANI:** ANIです。") == \
        {"ok": True, "blockers": []}


# ---------------------------------------------------------------- sidecar loading

def test_load_ear_both_spellings_and_corrupt(tmp_path):
    t = tmp_path / "t.txt"
    t.write_text("**Bose:** テスト。 ⚠", encoding="utf-8")
    assert load_ear(str(t)) is None                                    # no ledger -> None
    (tmp_path / "t.txt.ear.json").write_text('{"1": "k"}', encoding="utf-8")
    assert load_ear(str(t)) == {"1": "k"}
    assert ship_check_file(str(t))["ok"] is True
    t2 = tmp_path / "u.txt"
    t2.write_text("x ⚠", encoding="utf-8")
    (tmp_path / "u.ear.json").write_text('{"1": "k"}', encoding="utf-8")   # ext-swapped spelling
    assert load_ear(str(t2)) == {"1": "k"}
    t3 = tmp_path / "v.txt"
    t3.write_text("x ⚠", encoding="utf-8")
    (tmp_path / "v.txt.ear.json").write_text("{not json", encoding="utf-8")
    assert load_ear(str(t3)) is None                    # corrupt ledger never unlocks
    assert ship_check_file(str(t3))["ok"] is False


# ---------------------------------------------------------------- ./check --ship wrapper

def _run_check(*args):
    return subprocess.run([sys.executable, CHECK, *args],
                          capture_output=True, text=True, cwd=REPO)


def test_check_ship_refuses_exit_3_and_prints_no_grade(tmp_path):
    f = tmp_path / "draft.md"
    f.write_text("# T479 — DRAFT (verify by ear)\n"
                 "**?Bose:** はい。\n"
                 "**Staff:** テスト。 ⚠(要確認)\n", encoding="utf-8")
    p = _run_check(str(f), "--ship")
    assert p.returncode == 3
    assert "NOT SUBMITTABLE — 3 unresolved" in p.stdout
    for kind in ("draft_header", "unconfirmed_speaker", "unverified_span"):
        assert kind in p.stdout
    assert "GRADE" not in p.stdout          # the whole point: no grade on an unshippable file


def test_check_ship_clean_falls_through_to_grade(tmp_path):
    f = tmp_path / "done.txt"
    f.write_text("Speaker 1: This is a clean line.\nSpeaker 2: And so is this one.\n",
                 encoding="utf-8")
    p = _run_check(str(f), "--ship")
    assert p.returncode == 0
    assert "NOT SUBMITTABLE" not in p.stdout
    assert "GRADE" in p.stdout              # gate clear -> the normal QA audit ran


def test_check_ship_ear_sidecar_auto_loaded(tmp_path):
    f = tmp_path / "jp.txt"
    f.write_text("**Bose:** はい、テストです。 ⚠(表記ガイドライン次第)\n", encoding="utf-8")
    (tmp_path / "jp.txt.ear.json").write_text(json.dumps({"1": "k"}), encoding="utf-8")
    p = _run_check(str(f), "--ship")
    assert p.returncode == 0 and "GRADE" in p.stdout
    # same file without the ledger refuses — the sidecar is what proved the ear pass
    os.remove(tmp_path / "jp.txt.ear.json")
    p2 = _run_check(str(f), "--ship")
    assert p2.returncode == 3 and "NOT SUBMITTABLE — 1 unresolved" in p2.stdout


# ------------------------------------------------- earcheck -> ship SEAM (verifier-found critical)
# The two tools were built in parallel and disagreed on the ledger schema: earcheck writes
# {"resolved": [{"line_no", "decision": "keep"|"edit"|"unresolved"}], "total_flagged"} while the
# gate originally read only {line: initial} / [{"line": ...}] — so a COMPLETED ear pass still
# refused to ship (fails-closed, but pressures a gate bypass). This pins the seam end-to-end
# using earcheck's real writer and ship's real loader, never hand-built JSON.
def test_earcheck_ledger_clears_ship_gate(tmp_path):
    from transcript_truth.earcheck import _save_resolutions
    from transcript_truth.ship import load_ear, ship_check
    draft = tmp_path / "job.md"
    draft.write_text("**Bose:** はい、テスト。\n**ANI:** どうも。 ⚠(要確認)\n**SHINCO:** はい。 ⚠\n",
                     encoding="utf-8")
    _save_resolutions(str(draft) + ".ear.json",
                      [{"line_no": 2, "decision": "keep", "replacement": None},
                       {"line_no": 3, "decision": "edit", "replacement": "はい、SHINCOです。"}], 2)
    r = ship_check(draft.read_text(encoding="utf-8"), load_ear(str(draft)))
    assert r["ok"], f"ear-passed draft must ship, blockers: {r['blockers']}"


def test_earcheck_unresolved_blocks_ship_gate(tmp_path):
    from transcript_truth.earcheck import _save_resolutions
    from transcript_truth.ship import load_ear, ship_check
    draft = tmp_path / "job.md"
    draft.write_text("**Bose:** はい。\n**ANI:** どうも。 ⚠(要確認)\n", encoding="utf-8")
    _save_resolutions(str(draft) + ".ear.json",
                      [{"line_no": 2, "decision": "unresolved", "replacement": None}], 1)
    r = ship_check(draft.read_text(encoding="utf-8"), load_ear(str(draft)))
    assert not r["ok"]
    kinds = {b["kind"] for b in r["blockers"]}
    assert "unresolved_ear" in kinds and "unverified_span" in kinds
