"""The deterministic adjudicator ('brain') — word validity + collocation fit picking the correct
word, and its wiring into consensus_tokens so a linguistically-valid MINORITY beats a mediocre
majority. 'Models propose, code decides' applied to word choice.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.adjudicate import adjudicate, score
from transcript_truth.consensus import consensus_tokens


def test_real_word_beats_nonword():
    best, conf = adjudicate(["their", "thier"], ["house"], "en")
    assert best == "their" and conf >= 1.0


def test_two_nonwords_no_confidence():
    # neither is a real word -> judge can't tell -> low confidence -> defer to vote
    best, conf = adjudicate(["cogizzo", "kajizo"], ["account"], "en")
    assert conf < 1.0


def test_never_invents_only_ranks_given():
    best, _ = adjudicate(["cat", "dog"], [], "en")
    assert best in ("cat", "dog")


def test_empty_candidates():
    assert adjudicate([], [], "en") == ("", 0.0)


def test_adjudicator_overrides_majority_on_validity():
    # deepgram+gemini (2 families) agree on the NON-word 'thier'; scribe alone has 'their'.
    # vote-only keeps the majority non-word; the adjudicator picks the real word.
    reads = {"deepgram": "i saw thier house", "gemini": "i saw thier house",
             "scribe": "i saw their house"}
    assert consensus_tokens(reads)["text"] == "i saw thier house"          # vote only
    assert consensus_tokens(reads, "en")["text"] == "i saw their house"    # adjudicated


def test_records_override_span_when_backbone_is_wrong():
    # the most-reliable witness (scribe = the anchor) has the MISSPELLING; the others are right.
    # the misspelling is pruned and the correct word overrides the backbone -> span recorded.
    reads = {"scribe": "i saw thier house", "deepgram": "i saw their house",
             "gemini": "i saw their house"}
    r = consensus_tokens(reads, "en")
    assert r["text"] == "i saw their house"
    assert any(s.get("by") == "consensus" and s.get("to") == "their"
               for s in r["uncertain_spans"])


def test_no_lang_falls_back_to_vote():
    # without a language the judge is off -> pure family vote (back-compat)
    reads = {"deepgram": "i saw thier house", "gemini": "i saw thier house",
             "scribe": "i saw their house"}
    assert consensus_tokens(reads)["text"] == "i saw thier house"


def test_proper_name_beats_mishearing_via_frequency():
    # neither is a dictionary word; Tier 2: 'Kagiso' appears in web text, 'Cogizzo' does not
    best, conf = adjudicate(["Cogizzo", "Kagiso"], ["account"], "en")
    assert best == "Kagiso" and conf >= 1.0


def test_two_plausible_names_defer():
    # both 'Njoroge' and 'Jorg' are real names (both appear in text) -> can't tell -> defer
    best, conf = adjudicate(["Njoroge", "Jorg"], [], "en")
    assert conf < 1.0


def test_frequent_misspelling_still_loses_to_dictionary_word():
    # 'thier' is a FREQUENT misspelling (high zipf) but not a dictionary word; 'their' is -> Tier 1
    best, conf = adjudicate(["thier", "their"], ["house"], "en")
    assert best == "their" and conf >= 1.0


def test_clean_agreement_unaffected():
    reads = {"deepgram": "the cat sat", "gemini": "the cat sat", "scribe": "the cat sat"}
    assert consensus_tokens(reads, "en")["text"] == "the cat sat"
