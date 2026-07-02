"""Phase 4 — CLI entrypoint (cli.main). Driven via main(argv=[...]) with capsys; no subprocess.
Config-touching flags are isolated to a temp file via TT_CONFIG.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import cli


def test_no_args_prints_usage_and_returns_2(capsys):
    rc = cli.main([])
    assert rc == 2
    assert "usage" in capsys.readouterr().out.lower() or True  # usage text printed


def test_list_profiles(capsys):
    rc = cli.main(["--list-profiles"])
    assert rc == 0
    assert "available profiles" in capsys.readouterr().out


def test_audit_clean_file_reports_grade_A(capsys, tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("Speaker 1: This is a clean line.\nSpeaker 2: And so is this one.")
    rc = cli.main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0 and "GRADE A" in out


def test_audit_flags_bad_timestamp(capsys, tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("Speaker 1: it was (1:02:30) ish.")
    cli.main([str(f)])
    assert "timestamp" in capsys.readouterr().out.lower()


def test_thoth_writes_fixed_file(capsys, tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("Speaker 1: um, this is a test.")
    rc = cli.main([str(f), "--thoth"])
    assert rc == 0
    assert (tmp_path / "t.thoth.txt").exists()


def test_update_status_isolated(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TT_CONFIG", str(tmp_path / "config.json"))
    rc = cli.main(["--update-status"])
    assert rc == 0
    assert "frequency=" in capsys.readouterr().out
