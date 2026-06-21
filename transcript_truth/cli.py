from __future__ import annotations
import sys
from .engine import audit_transcript

_SEV = {"critical": "CRIT", "moderate": "WARN", "minor": "minor"}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "clean_verbatim"
    files = []
    for a in argv:
        if a in ("--full", "--full-verbatim"):
            mode = "full_verbatim"
        elif a.startswith("--mode="):
            mode = a.split("=", 1)[1]
        else:
            files.append(a)
    if not files:
        print("usage: python -m transcript_truth.cli <file.txt> [--full]")
        return 2

    path = files[0]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    r = audit_transcript(text, mode=mode)

    print()
    print("  transcript-truth — guideline-compliance receipt")
    print(f"  file: {path}    mode: {r.mode}    lines: {r.n_lines}")
    print("  " + "=" * 60)
    if not r.flags:
        print("  ✓ clean against the deterministic rule-set")
    for f in r.flags:
        print(f"  L{f.line:<3} [{_SEV[f.severity]:>5}] {f.label}")
        if f.evidence:
            print(f"           ↳ {f.evidence!r}")
        if f.fix:
            print(f"           fix: {f.fix}")
    print("  " + "=" * 60)
    print(f"  GRADE {r.grade}    ({r.math})")
    print("  No model in the verdict path — every flag is a deterministic rule hit.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
