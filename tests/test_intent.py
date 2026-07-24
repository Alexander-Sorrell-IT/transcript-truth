"""tt intent layer — garbled utterance -> registry-validated command.

Fully OFFLINE: the LLM is NEVER loaded here. An autouse fixture replaces
intent._llm_generate (the single funnel every backend goes through) with a
no-model stub; the LLM-path tests swap in canned strings to exercise the JSON
extraction + validate-merge logic without any model. The law under test: the
model only PROPOSES, validate() owns membership, the fallback is deterministic,
and nothing invalid ever reaches an argv.
"""
import importlib.machinery
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import intent

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """No test may ever load a model: kill the funnel, keyword path only."""
    monkeypatch.setattr(intent, "_llm_generate", lambda prompt: None)


def _tt():
    """Load the extensionless ./tt wrapper as a module (same trick a shebang
    plays). Fresh name so its module-globals are ours to monkeypatch."""
    loader = importlib.machinery.SourceFileLoader(
        "tt_wrapper", os.path.join(REPO, "tt"))
    spec = importlib.util.spec_from_loader("tt_wrapper", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- keyword fallback
# His REAL garbled style — every one must resolve without any model.

@pytest.mark.parametrize("utterance,action,args", [
    ("chek this japnse file for gotranscipt", "check",
     {"profile": "ja", "site": "gotranscript"}),
    ("ship it", "ship", {}),
    ("ar eth ears alive ja", "ears", {"lang": "ja"}),
    ("er check draft.md agianst audio.mp3", "earcheck",
     {"draft": "draft.md", "audio": "audio.mp3"}),
    ("er check it agianst the audio", "earcheck", {}),
    ("translat this japnse audio to en", "translate", {"src": "ja", "tgt": "en"}),
    ("translat this to englsh", "translate", {"tgt": "en"}),
    ("full verbtim chek", "check", {"mode": "full_verbatim"}),
    ("fix it", "check", {"fix": True}),
    ("list profils", "list-profiles", {}),
    ("coverge", "coverage", {}),
    ("chek medical en file", "check", {"profile": "en", "domain": "medical"}),
    ("shp job.txt", "ship", {"file": "job.txt"}),
    ("ship draft.txt with interview.mp3", "ship",
     {"file": "draft.txt", "audio": "interview.mp3"}),
])
def test_keyword_fallback_maps_garbled_utterances(utterance, action, args):
    r = intent.parse_intent(utterance)
    assert r["action"] == action
    assert r["args"] == args
    assert r["unrecognized"] == []          # every word placed or filler
    assert r["source"] == "keyword"
    assert r["confidence"] > 0


def test_explicit_files_fill_the_path_slots():
    r = intent.parse_intent("chek medical en", files=["notes.txt"])
    assert r["args"]["file"] == "notes.txt"
    r = intent.parse_intent("er check it agianst the audio",
                            files=["d.md", "a.mp3"])
    # audio extension feeds the audio slot regardless of argument order
    assert r["args"] == {"draft": "d.md", "audio": "a.mp3"}
    r = intent.parse_intent("er check it", files=["a.mp3", "d.md"])
    assert r["args"] == {"draft": "d.md", "audio": "a.mp3"}


def test_unplaceable_word_is_echoed_never_guessed():
    r = intent.parse_intent("chek job.txt xyzzyfoo")
    assert r["action"] == "check" and r["args"]["file"] == "job.txt"
    assert r["unrecognized"] == ["xyzzyfoo"]


def test_no_action_recognized_gives_none_and_zero_confidence():
    r = intent.parse_intent("hello wombat")
    assert r["action"] is None
    assert r["confidence"] == 0.0


def test_fallback_is_deterministic():
    a = intent.parse_intent("chek this japnse file for gotranscipt x.txt")
    b = intent.parse_intent("chek this japnse file for gotranscipt x.txt")
    assert a == b


def test_vocabulary_is_built_from_the_registries():
    # not a hardcoded list: whatever the registries hold NOW is the vocabulary
    from transcript_truth.profiles import names
    from transcript_truth.domains import domain_names, site_names
    v = intent.vocabulary()
    assert v["profiles"] == list(names())
    assert v["sites"] == list(site_names())
    assert v["domains"] == list(domain_names())
    assert "ja" in v["langs"] and set(v["lang_names"].values()) <= set(v["langs"])


# ---------------------------------------------------------------- validate (the wall)

def test_validate_rejects_hallucinated_profile():
    r = intent.validate({"action": "check",
                         "args": {"profile": "klingon", "site": "gotranscript"}})
    assert r["args"] == {"site": "gotranscript"}     # klingon NOT passed through
    assert "profile=klingon" in r["unrecognized"]


def test_validate_rejects_made_up_action_and_field():
    r = intent.validate({"action": "frobnicate", "args": {"file": "x.txt"}})
    assert r["action"] is None and r["args"] == {}
    assert "action=frobnicate" in r["unrecognized"]
    r = intent.validate({"action": "check", "args": {"sauce": "extra"}})
    assert r["args"] == {} and "sauce=extra" in r["unrecognized"]


def test_validate_alias_tables_are_deterministic_not_guesses():
    r = intent.validate({"action": "check", "args": {"mode": "full"}})
    assert r["args"]["mode"] == "full_verbatim"      # documented cli alias
    r = intent.validate({"action": "ears", "args": {"lang": "japanese"}})
    assert r["args"]["lang"] == "ja"                 # fixed name->code table
    r = intent.validate({"action": "check", "args": {"fix": "true"}})
    assert r["args"]["fix"] is True
    r = intent.validate({"action": "check", "args": {"mode": "sorta_verbatim"}})
    assert "mode" not in r["args"]                   # outside the closed pair
    assert "mode=sorta_verbatim" in r["unrecognized"]


def test_validate_recovers_flattened_model_args():
    # small models flatten args to the top level; known keys are recovered and
    # STILL membership-checked, unknown ones still surface
    r = intent.validate({"action": "check", "profile": "ja"})
    assert r["args"] == {"profile": "ja"}


# ---------------------------------------------------------------- render_command

def test_render_check_exact():
    argv, display = intent.render_command(
        {"action": "check",
         "args": {"file": "job.txt", "profile": "ja", "site": "gotranscript"}})
    assert argv == ["job.txt", "--profile=ja", "--site=gotranscript"]
    assert display == "check job.txt --profile=ja --site=gotranscript"


def test_render_check_full_flag_set_fixed_order():
    argv, display = intent.render_command(
        {"action": "check",
         "args": {"file": "a.txt", "profile": "en", "site": "rev",
                  "domain": "medical", "mode": "full_verbatim", "fix": True}})
    assert argv == ["a.txt", "--profile=en", "--site=rev", "--domain=medical",
                    "--mode=full_verbatim", "--fix"]
    assert display == ("check a.txt --profile=en --site=rev --domain=medical"
                       " --mode=full_verbatim --fix")


def test_render_ship_earcheck_ears_translate_coverage():
    assert intent.render_command(
        {"action": "ship", "args": {"file": "j.txt", "audio": "a.mp3"}}) == (
        ["j.txt", "--ship", "a.mp3"], "check j.txt --ship a.mp3")
    assert intent.render_command(
        {"action": "earcheck", "args": {"draft": "d.md", "audio": "a.mp3"}}) == (
        ["d.md", "a.mp3"], "earcheck d.md a.mp3")
    assert intent.render_command({"action": "ears", "args": {}}) == (
        ["--ears=ja"], "check --ears=ja")             # ja default, as ./check
    assert intent.render_command({"action": "ears", "args": {"lang": "ru"}}) == (
        ["--ears=ru"], "check --ears=ru")
    assert intent.render_command(
        {"action": "translate", "args": {"audio": "i.mp3", "src": "ja",
                                         "tgt": "en"}}) == (
        ["i.mp3", "--translate=en", "--src=ja"],
        "translate i.mp3 --src=ja --to=en")
    assert intent.render_command({"action": "coverage", "args": {}}) == (
        ["--coverage"], "coverage")
    assert intent.render_command({"action": "list-profiles", "args": {}}) == (
        ["--list-profiles"], "list-profiles")


def test_render_missing_required_shows_placeholder():
    argv, display = intent.render_command({"action": "earcheck", "args": {}})
    assert argv == ["<draft>", "<audio>"]
    assert display == "earcheck <draft> <audio>"


# ---------------------------------------------------------------- LLM path (stubbed)

def test_llm_json_is_extracted_from_prose(monkeypatch):
    messy = ("Sure! Here is the command you want:\n"
             '{"action": "ears", "args": {"lang": "ru"}}\n'
             "Let me know if that helps.")
    monkeypatch.setattr(intent, "_llm_generate", lambda prompt: messy)
    r = intent.parse_intent("ears alive ru")
    assert r["action"] == "ears" and r["args"] == {"lang": "ru"}
    assert r["source"] == "llm" and r["confidence"] == 0.9


def test_llm_hallucinated_field_falls_to_merged_keyword(monkeypatch):
    # invalid field INSIDE otherwise-good JSON: valid fields survive, the junk
    # surfaces in unrecognized, the keyword parse fills any gap
    messy = ("```json\n"
             '{"action": "check", "args": {"profile": "ja",'
             ' "site": "gotranscript", "sauce": "extra"}}\n```')
    monkeypatch.setattr(intent, "_llm_generate", lambda prompt: messy)
    r = intent.parse_intent("chek this japnse file for gotranscipt")
    assert r["action"] == "check"
    assert r["args"]["profile"] == "ja" and r["args"]["site"] == "gotranscript"
    assert "sauce=extra" in r["unrecognized"]
    assert r["source"] == "llm+keyword"


def test_llm_hallucinated_value_is_outvoted_by_keyword_merge(monkeypatch):
    monkeypatch.setattr(intent, "_llm_generate", lambda prompt:
                        '{"action": "check", "args": {"profile": "klingon"}}')
    r = intent.parse_intent("chek this japnse file")
    assert r["args"].get("profile") == "ja"          # keyword recovered it
    assert "profile=klingon" in r["unrecognized"]    # the invention is visible


def test_llm_clean_but_underdelivering_is_backfilled_from_keyword(monkeypatch):
    # live design finding: the real 1.5B emitted VALID JSON but dropped
    # "japnse" entirely — a clean model proposal must never silently LOSE a
    # field the deterministic registry match found
    monkeypatch.setattr(intent, "_llm_generate", lambda prompt:
                        '{"action":"check","args":{"site":"gotranscript"}}')
    r = intent.parse_intent("chek this japnse file for gotranscipt")
    assert r["args"] == {"site": "gotranscript", "profile": "ja"}
    assert r["source"] == "llm"


def test_llm_garbage_output_falls_to_pure_keyword(monkeypatch):
    monkeypatch.setattr(intent, "_llm_generate",
                        lambda prompt: "I have no idea { what you mean.")
    r = intent.parse_intent("ship it")
    assert r["action"] == "ship" and r["source"] == "keyword"


def test_extract_json_skips_stray_braces():
    got = intent._extract_json('blah { not json } then {"a": 1} end')
    assert got == {"a": 1}
    assert intent._extract_json("no json here") is None
    assert intent._extract_json("") is None


# ---------------------------------------------------------------- tt wrapper (REPL/confirm)

def test_tt_one_shot_confirm_y_dispatches(monkeypatch, capsys):
    tt = _tt()
    calls = []
    monkeypatch.setattr(tt, "_getch", lambda: "y")
    monkeypatch.setattr(tt, "dispatch", lambda a, argv: calls.append((a, argv)) or 0)
    rc = tt.main(["chek this japnse file for gotranscipt", "job.txt"])
    assert rc == 0
    assert calls == [("check", ["job.txt", "--profile=ja", "--site=gotranscript"])]
    out = capsys.readouterr().out
    assert "-> check job.txt --profile=ja --site=gotranscript" in out


def test_tt_confirm_n_never_dispatches(monkeypatch, capsys):
    tt = _tt()
    calls = []
    monkeypatch.setattr(tt, "_getch", lambda: "n")
    monkeypatch.setattr(tt, "dispatch", lambda a, argv: calls.append((a, argv)) or 0)
    rc = tt.main(["shp job.txt"])
    assert rc == 0 and calls == []
    assert "not run" in capsys.readouterr().out


def test_tt_echoes_unplaced_words_and_still_asks(monkeypatch, capsys):
    tt = _tt()
    calls = []
    monkeypatch.setattr(tt, "_getch", lambda: "n")
    monkeypatch.setattr(tt, "dispatch", lambda a, argv: calls.append(a) or 0)
    tt.main(["chek job.txt xyzzyfoo"])
    out = capsys.readouterr().out
    assert "couldn't place: 'xyzzyfoo'" in out
    assert calls == []                               # asked, declined, no run


def test_tt_refuses_to_run_without_required_file(monkeypatch, capsys):
    tt = _tt()
    calls = []
    # _getch would explode if consulted — refusal must come BEFORE any keypress
    monkeypatch.setattr(tt, "_getch",
                        lambda: (_ for _ in ()).throw(AssertionError("asked")))
    monkeypatch.setattr(tt, "dispatch", lambda a, argv: calls.append(a) or 0)
    rc = tt.main(["er check it agianst the audio"])
    assert rc == 2 and calls == []
    out = capsys.readouterr().out
    assert "need: <draft>, <audio>" in out


def test_tt_repl_dispatches_then_quits_on_q(monkeypatch, capsys):
    tt = _tt()
    calls = []
    lines = iter(["coverge", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))
    monkeypatch.setattr(tt, "_getch", lambda: "y")
    monkeypatch.setattr(tt, "dispatch", lambda a, argv: calls.append((a, argv)) or 0)
    rc = tt.main([])                                 # bare tt = REPL
    assert rc == 0
    assert calls == [("coverage", ["--coverage"])]
    assert "-> coverage" in capsys.readouterr().out


def test_tt_repl_unknown_action_keeps_listening(monkeypatch, capsys):
    tt = _tt()
    calls = []
    lines = iter(["hello wombat", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))
    monkeypatch.setattr(tt, "_getch", lambda: "y")
    monkeypatch.setattr(tt, "dispatch", lambda a, argv: calls.append(a) or 0)
    assert tt.main([]) == 0 and calls == []
    assert "no action recognized" in capsys.readouterr().out


# ------------------------------------------------- verifier-found gaps (2026-07-24), pinned
def test_flag_shaped_path_is_rejected_not_reparsed():
    # file='--update' passed the wall and was re-parsed downstream as a FLAG — running a
    # different action (plugin update, which WRITES files) under a 'check x' display line.
    from transcript_truth.intent import validate, vocabulary
    v = validate({"action": "check", "args": {"file": "--update"}, "unrecognized": []},
                 vocabulary())
    assert not v["args"].get("file")
    assert any("--update" in str(u) for u in v["unrecognized"])


def test_malformed_llm_shape_degrades_to_keyword(monkeypatch):
    # valid JSON, wrong SHAPE (args as a list) from a real 1.5B: must fall back to the
    # keyword parse, never crash tt with a traceback.
    from transcript_truth import intent
    monkeypatch.setattr(intent, "_llm_propose",
                        lambda *a, **k: {"action": "check", "args": ["x.txt"]})
    cfg = intent.parse_intent("chek this japnse file x.txt")
    assert cfg["source"] == "keyword" and cfg["action"] == "check"
    assert cfg["args"].get("profile") == "ja"


def test_ship_never_steals_audio_file_for_text_slot():
    # 'ship … interview.mp3': the text 'file' slot must stay EMPTY (honest 'need: <file>'),
    # not receive an audio file that check would then read as UTF-8.
    from transcript_truth.intent import parse_intent
    cfg = parse_intent("shp the fnised draft wth the interview.mp3")
    assert cfg["action"] in ("ship", "check")
    assert cfg["args"].get("file") != "interview.mp3"
