"""Phase 8 — CLI wiring for the translation track (cli.main --translate).

OFFLINE ONLY: translate.translate (and language.detect) are MONKEYPATCHED to canned values.
No real model/network is ever called. Asserts the CLI parses --translate, dispatches to the
translation path, prints the text + FLAGGED status + the verifiability (review) surface, and
leaves the transcription/audit path untouched.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import cli
import transcript_truth.translate as translate_mod
import transcript_truth.language as language_mod


def _fake_translate(calls, **overrides):
    """Factory: a canned translate() that records how the CLI called it."""
    def fake(audio_path, src_lang, tgt_lang="en", transcript=None, **k):
        calls["args"] = (audio_path, src_lang, tgt_lang)
        r = {
            "text": "There were 17 people in Cairo.",
            "alt": "17 people were in Cairo.",
            "agreement": 0.91,
            "flagged": False,
            "checks": {"ok": True, "numbers_verifiable": True, "names_verifiable": True,
                       "missing_numbers": [], "introduced_numbers": [], "missing_names": [],
                       "passed": 2, "total": 2},
            "checks_alt": None,
            "transcript": "17 kisi vardi.",
            "src_lang": src_lang, "tgt_lang": tgt_lang,
        }
        r.update(overrides)
        return r
    return fake


def test_translate_flag_dispatches_and_prints(capsys, monkeypatch):
    calls = {}
    monkeypatch.setattr(translate_mod, "translate", _fake_translate(calls))
    rc = cli.main(["/tmp/fake.wav", "--translate=es", "--src=tr"])
    out = capsys.readouterr().out
    assert rc == 0
    # parsed --translate=es and --src=tr, dispatched with the audio path
    assert calls["args"] == ("/tmp/fake.wav", "tr", "es")
    assert "translation receipt" in out.lower()
    assert "There were 17 people in Cairo." in out
    assert "confident" in out.lower()          # not flagged


def test_translate_default_target_is_en(capsys, monkeypatch):
    calls = {}
    monkeypatch.setattr(translate_mod, "translate", _fake_translate(calls))
    rc = cli.main(["/tmp/fake.wav", "--translate", "--src=tr"])
    assert rc == 0
    assert calls["args"] == ("/tmp/fake.wav", "tr", "en")


def test_translate_autodetects_source_when_no_src(capsys, monkeypatch):
    """No --src and profile is the non-language default -> must auto-detect, never pass 'default'."""
    calls = {}
    monkeypatch.setattr(translate_mod, "translate", _fake_translate(calls))
    monkeypatch.setattr(language_mod, "detect", lambda p, **k: "tr")
    rc = cli.main(["/tmp/fake.wav", "--translate=es"])
    assert rc == 0
    assert calls["args"][1] == "tr"            # detected language, not the "default" profile


def test_translate_surfaces_flags_and_unverifiable(capsys, monkeypatch):
    """A flagged clip with a dropped number and a non-Latin (unverifiable) name check must
    surface the failure AND the uncertainty — never a silent green."""
    calls = {}
    flagged = _fake_translate(
        calls,
        flagged=True,
        agreement=0.40,
        checks={"ok": False, "numbers_verifiable": True, "names_verifiable": False,
                "missing_numbers": ["17"], "introduced_numbers": [], "missing_names": [],
                "passed": 0, "total": 1},
    )
    monkeypatch.setattr(translate_mod, "translate", flagged)
    rc = cli.main(["/tmp/ar.wav", "--translate=en", "--src=ar"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "FLAGGED" in out
    assert "17" in out and "dropped numbers" in out.lower()
    assert "names verifiable: False" in out
    assert "review" in out.lower()             # the unverifiable-name review surface


def test_translate_handles_empty_witnesses(capsys, monkeypatch):
    """Both witnesses empty -> checks is None; receipt must not crash and must flag."""
    calls = {}
    empty = _fake_translate(calls, text="", flagged=True, checks=None, agreement=0.0)
    monkeypatch.setattr(translate_mod, "translate", empty)
    rc = cli.main(["/tmp/x.wav", "--translate=es", "--src=tr"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no translation produced" in out.lower()
    assert "FLAGGED" in out


def test_audit_path_unchanged_without_translate(capsys, tmp_path, monkeypatch):
    """--translate is additive: a normal text file still audits (translation never invoked)."""
    def boom(*a, **k):
        raise AssertionError("translate() must not be called on the audit path")
    monkeypatch.setattr(translate_mod, "translate", boom)
    f = tmp_path / "t.txt"
    f.write_text("Speaker 1: This is a clean line.\nSpeaker 2: And so is this one.")
    rc = cli.main([str(f)])
    out = capsys.readouterr().out
    assert rc == 0 and "GRADE" in out
