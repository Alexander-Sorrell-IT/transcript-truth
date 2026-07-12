#!/usr/bin/env python3
"""Site (vendor) scaffold (PERFECTION_PLAN VI) — a site plugin is only real when it has rules
FROM THE VENDOR'S OWN STYLE GUIDE plus tests proving conflicting vendors flip verdicts.

    python3 scripts/new_site.py <name> [--check]

Enforced steps:
  1. rules module transcript_truth/<name>_rules.py (skeleton written if missing)
  2. register_site(...) in domains.py (by hand — read the vendor's PUBLIC style guide first;
     an invented format is worse than none: it would grade output against rules the vendor
     never wrote)
  3. tests: tests/ must reference the site (flip-verdict test vs at least one other vendor)
--check reports missing steps.
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def status(name: str) -> dict:
    from transcript_truth.domains import SITE_REGISTRY
    tests = False
    for tf in glob.glob(os.path.join(ROOT, "tests", "*.py")):
        if name in open(tf, encoding="utf-8").read():
            tests = True
            break
    return {
        "rules_module": os.path.exists(os.path.join(ROOT, "transcript_truth", f"{name}_rules.py")),
        "registered": name in SITE_REGISTRY,
        "tests": tests,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    name = args[0].lower()
    st = status(name)
    if "--check" in sys.argv:
        for k, v in st.items():
            print(f"  {'OK ' if v else 'MISSING'} {k}")
        done = all(st.values())
        print(f"\n{name}: {'REGISTERED' if done else 'NOT DONE — no guide, no tests, no site'}")
        sys.exit(0 if done else 1)
    if not st["rules_module"]:
        p = os.path.join(ROOT, "transcript_truth", f"{name}_rules.py")
        open(p, "w", encoding="utf-8").write(
            f'"""{name} site rules — SCAFFOLD. Encode the vendor\'s PUBLIC style guide here; '
            f'cite the guide URL/version in this docstring."""\n')
        print(f"wrote skeleton {p}")
    for k, todo in (("registered", f"register_site('{name}', ...) in domains.py citing the guide"),
                    ("tests", "add a flip-verdict test (same text, two vendors, different grades)")):
        if not st[k]:
            print("TODO:", todo)


if __name__ == "__main__":
    main()
