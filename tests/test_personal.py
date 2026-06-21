"""Personal profile tests — Alex's missing-apostrophe slips, layered on legal.
Deterministic = testable. The 'me' profile must keep all legal behavior AND add
the personal apostrophe checks, without flagging clean text."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import audit_transcript


def _rules(text):
    return {f.rule for f in audit_transcript(text, profile="me").flags}


# --- the personal slips it must catch ---

def test_missing_apostrophe_contractions():
    for w in ("dont", "didnt", "wouldnt", "youre", "theyre", "thats", "theres"):
        assert "me_apostrophe" in _rules(f"A    I {w} know."), w

def test_im_lowercase():
    assert "me_apostrophe" in _rules("A    im going to the store.")

def test_ambiguous_cant_wont_are_review():
    flags = audit_transcript("A    I cant and I wont.", profile="me").flags
    review = [f for f in flags if f.rule == "me_apostrophe" and f.severity == "review"]
    assert len(review) == 2

# --- legal behavior must still ride along ---

def test_legal_still_applies_in_me_profile():
    assert "legal_spelling" in _rules("A    He said OK.")          # p.5 via legal
    assert "legal_grammar" in _rules("A    It's you're cabin.")     # your/you're via legal

# --- clean text must stay clean (precision) ---

def test_clean_contractions_not_flagged():
    # properly apostrophe'd, and the real words 'can't'/'won't' written correctly
    assert _rules("A    I don't know, but that's fine and I'm okay.") == set()

def test_real_word_him_team_not_flagged():
    # 'im' must not fire inside other words
    assert _rules("A    I told him the team won.") == set()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
