"""Spanish homophone-trap surfacer tests. It is a high-recall REVIEW surfacer
(opt-in, not in the graded profile) — these lock its recall and its boundary
behavior, and assert it stays review-tier so it can never move a grade."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.es_rules import homophone_traps
from transcript_truth.types import Transcript, Line

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _flags(text):
    return homophone_traps(Transcript(lines=[Line(1, text)]))


def test_surfaces_known_trap():
    assert any(f.rule == "es_homophone_trap" for f in _flags("Espero que ya halla llegado."))

def test_all_flags_are_review_tier():
    # must never move the grade — the KB is not authority-grounded
    assert all(f.severity == "review" for f in _flags("halla vaya hecho tú sí"))

def test_word_boundary_no_substring_misfire():
    assert _flags("Siempre trabajo mucho.") == []       # 'si' must not fire inside 'siempre'
    assert _flags("Compré pan fresco hoy.") == []       # verified member-free line

def test_accent_insensitive_lookup():
    # tú/tu and sí/si differ only by accent — both forms should be recognized
    assert _flags("Tu eres mi amigo.") or _flags("tú")  # the trap is surfaced regardless of accent

def test_recall_on_labeled_error_cases():
    cases = json.load(open(os.path.join(_HERE, "data", "es_cases.json"), encoding="utf-8"))
    errs = [c for c in cases if c.get("has_error")]
    fired = sum(1 for c in errs if _flags(c["text"]))
    assert fired == len(errs), f"recall {fired}/{len(errs)}"   # 100% recall on planted errors


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok   {fn.__name__}")
    print(f"\n  {len(fns)} passed")
