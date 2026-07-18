"""Japanese now has its OWN registered profile + a GoTranscript Japanese site layer.
Offline, no model. Pins routing, registration, the punctuation rule's zero-FP guards, and that the
gotranscript × ja coverage slot flipped core -> full."""
from transcript_truth.types import Transcript, Line
from transcript_truth.ja_rules import japanese_punctuation
from transcript_truth.language import profile_for
from transcript_truth.profiles import names, get
from transcript_truth.domains import coverage_report, compose


def _t(text):
    return Transcript(lines=[Line(i + 1, s) for i, s in enumerate(text.split("\n"))])


# --- routing + registration: ja is a first-class language now, not `default` ---
def test_ja_routes_to_ja_not_default():
    assert profile_for("ja") == "ja"
    assert profile_for("ja-JP") == "ja"


def test_ja_profile_registered():
    assert "ja" in names()
    assert "ja:full" in names()
    assert get("jp").name == "ja"           # alias
    # substantive: it carries the kana-usage crown jewel, not an empty rule set
    assert get("ja").scanners


# --- the Japanese punctuation rule FIRES on real errors ---
def test_flags_ascii_period_after_japanese():
    flags = japanese_punctuation(_t("今日は晴れです."))
    assert any(f.rule == "ja_punct" for f in flags)


def test_flags_ascii_comma_after_japanese():
    flags = japanese_punctuation(_t("そうですね,行きましょう"))
    assert any(f.rule == "ja_punct" for f in flags)


# --- and does NOT false-fire (the guards) ---
def test_no_fp_on_decimal():
    assert japanese_punctuation(_t("価格は3.14ドルです")) == [] or \
        all("3." not in f.evidence for f in japanese_punctuation(_t("価格は3.14ドルです")))


def test_no_fp_on_english_abbrev_number_url():
    for s in ["Mr. Tanaka came", "It cost 1,000 yen", "See example.co.jp today", "Version 2.0 shipped"]:
        assert japanese_punctuation(_t(s)) == [], f"false positive on: {s}"


def test_no_fp_on_clean_japanese_with_correct_punctuation():
    assert japanese_punctuation(_t("今日は晴れです。そうですね、行きましょう。")) == []


# --- the plugin wiring: gotranscript × ja slot is now `full` ---
def test_gotranscript_ja_slot_is_full():
    rows = {(r["language"], r["layer"]): r["coverage"] for r in coverage_report()}
    assert rows.get(("ja", "gotranscript")) == "full"


def test_compose_ja_gotranscript_includes_both_layers():
    prof = compose("ja", None, "gotranscript")
    names_ = {getattr(s, "__name__", "") for s in prof.scanners}
    assert "kana_usage" in names_          # language rule (from ja profile)
    assert "japanese_punctuation" in names_  # site format rule (from gotranscript_ja layer)
