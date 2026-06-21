"""Thoth (deterministic auto-fix) tests. Profile-agnostic: legal, me, default.
Every fix is a regex hit applied via re.sub — testable, no model."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import audit_transcript
from transcript_truth.thoth import thoth


def fix(text, profile):
    return thoth(text, profile)[0]


# --- legal (CVL "Redline") ---

def test_legal_spelling():
    assert fix("A    He said OK.", "legal") == "A    He said okay."

def test_legal_us_and_email():
    assert fix("A    A U.S. e-mail.", "legal") == "A    A US email."

def test_legal_youre_possessive():
    assert fix("A    It's you're cabin.", "legal") == "A    It's your cabin."

def test_legal_filler_removed():
    assert fix("A    Uh, I think so.", "legal") == "A    I think so."

def test_legal_percent_and_ampm():
    assert fix("A    It was 50% at 5:30 p.m. today.", "legal") == \
        "A    It was 50 percent at 5:30 PM today."

def test_legal_title_mrs():
    assert fix("THE COURT    We have Mrs. Carmody here.", "legal") == \
        "THE COURT    We have Ms. Carmody here."

def test_legal_label_gap_preserved():
    # the colloquy gap (multi-space) must survive cleanup
    assert fix("MR. JONES    OK.", "legal") == "MR. JONES    okay."

# --- me (personal apostrophes on top of legal) ---

def test_me_apostrophes():
    assert fix("A    im sure i dont know.", "me") == "A    I'm sure i don't know."

def test_me_review_tier_not_autofixed():
    # cant is review-tier (collides with the real word) -> left for the human
    assert "cant" in fix("A    I cant go.", "me")

# --- default (Japanese + GoTranscript English) ---

def test_default_english_filler():
    assert fix("Speaker 1: um, this is it.", "default") == "Speaker 1: this is it."

def test_default_keeps_crutch_phrase():
    # 'kind of' is context-dependent -> NOT auto-removed by Thoth (stays a flag)
    assert "kind of" in fix("Speaker 1: it was kind of blue.", "default")

# --- properties ---

def test_idempotent():
    once = fix("A    He said OK, U.S. citizen, its you're cabin.", "legal")
    assert fix(once, "legal") == once

def test_grade_improves():
    bad = "A    He said OK, U.S. citizen, 50% sure."
    before = audit_transcript(bad, profile="legal").grade
    after = audit_transcript(fix(bad, "legal"), profile="legal").grade
    assert after <= before  # grades sort A<B<...<F; improvement moves toward 'A'


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
