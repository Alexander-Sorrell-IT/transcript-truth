#!/usr/bin/env python3
"""Language scaffold (PERFECTION_PLAN VI) — adding a language touches 4 places; this generates
the skeleton and REFUSES the final registration step until a battery score exists (the Urdu
lesson: wired-but-unvalidated sat for a week looking done).

    python3 scripts/new_language.py <code> [--check]

Steps it enforces, in order:
  1. profile module transcript_truth/<code>_rules.py (skeleton written if missing)
  2. ROSTER entry in consensus.py (told, not auto-edited — a roster is a design decision)
  3. battery clips bench/battery/fp_<code>*.json+wav (make_multilang_battery pattern)
  4. live bench -> reliability row (build_reliability.py)
--check reports which steps are missing; registration is 'done' ONLY when all four exist.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _has_profile(code: str) -> bool:
    """The ENGINE's registry is the truth, not a filename convention (ur lives in profiles/ur.py,
    ru rules in cyrillic_rules.py — shared modules are fine)."""
    try:
        from transcript_truth.engine import audit_transcript
        r = audit_transcript("test", profile=code)
        return True
    except Exception:
        return False


def status(code: str) -> dict:
    from transcript_truth.consensus import ROSTER
    rel = {}
    try:
        rel = json.load(open(os.path.join(ROOT, "data", "witness_reliability.json")))
    except Exception:
        pass
    return {
        "profile_module": _has_profile(code),
        "roster": code in ROSTER,
        "battery": bool(glob.glob(os.path.join(ROOT, "bench", "battery", f"fp_{code}*.json"))),
        "reliability_measured": code in rel,
    }


SKELETON = '''"""{code} language rules — SCAFFOLD (generated; replace with real rules).
A language profile = roster (consensus.ROSTER) + tokenizer defaults + deterministic rules.
This module registers the {code} audit profile; add lexicon/rules as they are built."""
from .types import Flag, Transcript


def {code}_placeholder_scanner(t: Transcript) -> list[Flag]:
    """No {code}-specific rules yet — scaffold. Replace before claiming the language."""
    return []
'''


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    code = args[0].lower()
    st = status(code)
    if "--check" in sys.argv:
        for k, v in st.items():
            print(f"  {'OK ' if v else 'MISSING'} {k}")
        done = all(st.values())
        print(f"\n{code}: {'REGISTERED (all four steps measured)' if done else 'NOT DONE — an unmeasured language is not a language'}")
        sys.exit(0 if done else 1)

    if not st["profile_module"]:
        p = os.path.join(ROOT, "transcript_truth", f"{code}_rules.py")
        open(p, "w", encoding="utf-8").write(SKELETON.format(code=code))
        print(f"wrote skeleton {p}")
    if not st["roster"]:
        print(f"TODO (by hand — a design decision): add '{code}' to consensus.ROSTER "
              f"and language.PROFILE_FOR")
    if not st["battery"]:
        print(f"TODO: generate battery clips (see bench/make_multilang_battery.py / "
              f"make_real_battery.py) -> bench/battery/fp_{code}*.json")
    if not st["reliability_measured"]:
        print("TODO: run the live bench, then bench/build_reliability.py — "
              "REGISTRATION IS NOT DONE UNTIL THIS ROW EXISTS")
    print("\nrun with --check to verify; all four must pass before the language is claimed.")


if __name__ == "__main__":
    main()
