"""The 10 CVL coverage-gap scanners (guide p.3-24) — each fires on its violation, silent on clean."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from transcript_truth.legal_rules import (
    legal_dash_form, legal_repeated_words, legal_partial_words, legal_money_numerals,
    legal_decade_apostrophe, legal_date_commas, legal_conjunction_comma, legal_quote_punct,
    legal_spoken_punct, legal_speaker_ids)
from transcript_truth.types import Transcript, Line


def T(s):
    return Transcript(lines=[Line(n=1, text=s)])


CASES = [
    (legal_dash_form, "I was going — wait.", "So I went home."),
    (legal_repeated_words, "Do we want to want to go?", "It was very, very cold."),
    (legal_repeated_words, "I went to the the store.", "I know that that is true."),
    (legal_partial_words, "The cat was bl- white.", "That is well-known law."),
    (legal_money_numerals, "He paid twenty dollars for it.", "He paid $20 for it."),
    (legal_decade_apostrophe, "Back in the 70's it was fine.", "Back in the '70s it was fine."),
    (legal_date_commas, "That was June, 2020 I believe.", "That was June 2020 I believe."),
    (legal_conjunction_comma, "So, I decided to leave.", "So I decided to leave."),
    (legal_quote_punct, 'She said, "hello".', 'She said, "hello."'),
    (legal_spoken_punct, "runny nose, comma, sore throat.", "runny nose, sore throat."),
    (legal_speaker_ids, "Mr. Smith: I object.", "MR. SMITH: I object."),
]


@pytest.mark.parametrize("fn,bad,good", CASES, ids=[f"{c[0].__name__}-{i}" for i, c in enumerate(CASES)])
def test_fires_on_violation_silent_on_clean(fn, bad, good):
    assert fn(T(bad)), f"{fn.__name__} should flag {bad!r}"
    assert not fn(T(good)), f"{fn.__name__} false-fired on {good!r}"
