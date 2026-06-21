"""TranscribeMe CV-for-Legal profile — golden tests drawn from the style guide's
own Said->Type / No->Yes tables. Deterministic = testable."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import audit_transcript


def _rules(text):
    return {f.rule for f in audit_transcript(text, profile="legal").flags}


# --- things the SG says to FIX (must flag) ---

def test_okay_spelling():            # p.5: OK/'kay -> okay
    assert "legal_spelling" in _rules("A    He said OK.")

def test_alright_alot():             # p.5
    assert "legal_spelling" in _rules("A    It was alright, alot of times.")

def test_us_periods():               # p.5: U.S. -> US
    assert "legal_spelling" in _rules("A    I am a U.S. citizen.")

def test_email_healthcare():         # p.5
    assert "legal_spelling" in _rules("A    Send an e-mail about health care.")

def test_slang_standard_forms():     # p.9
    for w in ("gonna", "wanna", "coulda", "cuz", "sorta"):
        assert "legal_slang" in _rules(f"A    I was {w} there."), w

def test_contraction_exceptions():   # p.8
    assert "legal_contraction" in _rules("A    I would've gone.")

def test_hesitations_removed():      # p.10
    for w in ("uh", "um", "ah", "er"):
        assert "legal_filler" in _rules(f"A    {w}, I think so."), w

def test_nonverbal_mapped():         # p.11
    assert "legal_nonverbal" in _rules("A    He just went mm-hmm.")

def test_title_mrs_miss():           # p.12
    assert "legal_title" in _rules("THE COURT    We have Mrs. Carmody here.")
    assert "legal_title" in _rules("A    That was Miss Lewis.")

def test_percent_symbol():           # p.14
    assert "legal_number" in _rules("A    It was 50% of the time.")

def test_accented_letters():         # p.24
    assert "legal_accent" in _rules("A    My fiancee said sí in Cañon City.")

def test_ampm():                     # p.16
    assert "legal_ampm" in _rules("A    It was 5:30 p.m.")

def test_inaudible_brackets_and_case():  # p.13/24
    assert "legal_tag" in _rules("A    We saw (inaudible) there.")
    assert "legal_tag" in _rules("A    We saw [Inaudible] there.")

def test_grammar_youre_your():           # [grammar] — the exam your/you're case
    assert "legal_grammar" in _rules("A    It's you're cabin in the woods.")
    assert "legal_grammar" in _rules("A    It should be you're responsibility to clean it.")

def test_grammar_of_for_have():          # [grammar]
    for w in ("could of", "should of", "would of", "must of"):
        assert "legal_grammar" in _rules(f"A    I {w} known."), w

def test_grammar_homophone_possessives():  # [grammar]
    assert "legal_grammar" in _rules("A    It was there own fault.")     # their
    assert "legal_grammar" in _rules("A    The dog hurt it's own paw.")  # its


# --- things the SG says are CORRECT (must NOT flag) ---

def test_keeps_contractions_and_slang_exceptions():   # p.9
    assert _rules("A    Well, y'all ain't going to believe this, but I'ma tell him.") == set()

def test_yeah_and_okay_both_allowed():                # p.5/p.9
    assert _rules("Q    Yeah, okay. So that was the only reason?") == set()

def test_crutch_words_kept():                         # p.10
    assert _rules("A    You know, I mean, it was, like, the same thing.") == set()

def test_correct_inaudible_is_clean():                # p.13
    assert "legal_tag" not in _rules("A    We saw [inaudible] there.")

def test_gotcha_and_could_have_clean():               # p.8/p.9
    assert _rules("A    Gotcha. He could have just gone.") == set()

def test_colloquy_label_gap_not_double_space():       # p.3
    assert _rules("MR. JONES    I am Don Jones appearing for the Plaintiff.") == set()

def test_grammar_correct_homophones_clean():          # [grammar] precision guard
    # right homophone + the contractions that look similar must NOT hard-flag
    assert _rules("A    You're going to your house, and they're at their car.") == set()
    assert _rules("A    He could have known it was its own fault.") == set()

def test_default_profile_unaffected():
    # legal rules must not leak into the default profile (regression guard)
    r = audit_transcript("Speaker 1: This is a clean line.")
    assert r.grade == "A" and r.flags == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
