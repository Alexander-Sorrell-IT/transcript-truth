"""Phase 4 — pure lexical layers: semantic (JP homophone traps), lexicon (unknown-word +
confusable surfacers), collocation (content-word coherence). Real dictionaries, no models.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.types import Transcript, Line
from transcript_truth import semantic, lexicon, collocation


# ---------- semantic.homophone_traps ----------

def test_homophone_trap_surfaced_for_known_member():
    # 対象 is a member of a known trap set -> surfaced for review
    t = Transcript(lines=[Line(n=1, text="対象を選ぶ")])
    flags = semantic.homophone_traps(t)
    assert any(f.evidence == "対象" for f in flags)


def test_homophone_traps_clean_line():
    t = Transcript(lines=[Line(n=1, text="hello world")])
    assert semantic.homophone_traps(t) == []


# ---------- lexicon ----------

def test_is_known_true_for_common_word():
    assert lexicon.is_known("house", "en") is True


def test_is_known_false_for_garble():
    assert lexicon.is_known("qwzxvbn", "en") is False


def test_unknown_word_scanner_flags_garble():
    scan = lexicon.make_unknown_word("en")
    t = Transcript(lines=[Line(n=1, text="the qwzxvbn ran fast")])
    flags = scan(t)
    assert any(f.evidence == "qwzxvbn" for f in flags)


def test_unknown_word_scanner_spares_common_words():
    scan = lexicon.make_unknown_word("en")
    t = Transcript(lines=[Line(n=1, text="the quick brown fox jumps")])
    assert scan(t) == []


def test_make_confusables_returns_callable_scanner():
    scan = lexicon.make_confusables("en")
    assert callable(scan)
    # runs without error on a plain line
    scan(Transcript(lines=[Line(n=1, text="a normal sentence")]))


# ---------- collocation ----------

def test_colloc_content_extraction_runs():
    # coherence_report should run and return a structure over content words
    rep = collocation.coherence_report("契約書の内容を確認する")
    assert rep is not None
