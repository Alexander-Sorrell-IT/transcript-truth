"""Legal-as-cross-language tests: the legal style composes onto any language."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import audit_transcript, profile_names


def _rules(text, profile):
    return {f.rule for f in audit_transcript(text, profile=profile).flags}


def test_composed_profiles_registered():
    n = profile_names()
    assert {"legal:en", "legal:ja", "legal:es"} <= set(n), n

def test_legal_en_matches_legal():
    # legal:en is the full CVL set — same behavior as the original legal profile
    line = "A    OK, send an e-mail to the U.S. office."
    assert _rules(line, "legal:en") == _rules(line, "legal")

def test_legal_ja_runs_japanese_checks():
    # Japanese kana-rule violation flagged under legal:ja (English CVL never would)
    assert "kana_usage" in _rules("歩く事ができる。", "legal:ja")

def test_legal_core_is_language_agnostic():
    # the agnostic formatting core (bracket tags) fires regardless of language
    assert "legal_tag" in _rules("これは (inaudible) です。", "legal:ja")

def test_legal_es_produces_receipt():
    # ES has only the agnostic core for now, but the profile composes + runs
    r = audit_transcript("Hola, esto es una prueba.", profile="legal:es")
    assert r.grade in ("A", "B", "C", "D", "F")

def test_existing_legal_profile_unchanged():
    # additive change must not alter the original profile
    assert "legal_spelling" in _rules("A    He said OK.", "legal")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
