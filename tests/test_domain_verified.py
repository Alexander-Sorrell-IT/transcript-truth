"""Phase G — legal/medical re-examination loop (MODEL_MAP.md Stage 4).

Transcribe -> audit vs the domain guide -> if a critical term is still flagged, re-read + re-audit
up to max_rounds. Real legal scanners; the transcribe step is injected to simulate passes.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.runner import transcribe_domain_verified

_BAD = "The subpena and the defendent."       # legal_term fires (misspellings)
_GOOD = "The subpoena and the defendant."     # clean


def _seq(*texts):
    """A no-arg transcribe_fn returning the given texts across successive calls."""
    it = iter(texts)
    last = [None]
    def fn():
        try:
            last[0] = next(it)
        except StopIteration:
            pass
        return {"text": last[0]}
    return fn


def test_reread_resolves_critical_term():
    # round 1 bad -> critical flag -> re-read -> round 2 good -> resolved
    r = transcribe_domain_verified("x.wav", "en", "legal", transcribe_fn=_seq(_BAD, _GOOD))
    assert r["rounds"] == 2 and r["resolved"] is True
    assert r["remaining_flags"] == [] and r["content"] == _GOOD


def test_clean_first_pass_stops_at_round_one():
    r = transcribe_domain_verified("x.wav", "en", "legal", transcribe_fn=_seq(_GOOD, _GOOD))
    assert r["rounds"] == 1 and r["resolved"] is True


def test_unresolved_after_max_rounds_surfaces_flags():
    # stays bad (but changes each round so it doesn't early-stop) -> exhausts rounds, unresolved
    r = transcribe_domain_verified("x.wav", "en", "legal",
                                   transcribe_fn=_seq("The subpena here.", "The defendent there."))
    assert r["rounds"] == 2 and r["resolved"] is False
    assert any(f.rule == "legal_term" for f in r["remaining_flags"])


def test_stable_unchanged_reread_stops_early():
    # re-read returns the SAME bad text -> stop (no point re-reading), unresolved
    r = transcribe_domain_verified("x.wav", "en", "legal", transcribe_fn=_seq(_BAD, _BAD))
    assert r["rounds"] == 2 and r["resolved"] is False
