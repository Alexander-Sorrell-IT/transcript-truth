from __future__ import annotations
import sys
from .engine import audit_transcript
from .profiles import REGISTRY, names

_SEV = {"critical": "CRIT", "moderate": "WARN", "minor": "minor", "review": "check"}

_USAGE = ("usage: python -m transcript_truth.cli <file.txt> [--profile=legal] [--full] [--thoth]\n"
          "       python -m transcript_truth.cli --list-profiles\n"
          "  --thoth   apply deterministic auto-fixes -> writes <file>.thoth.txt")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "clean_verbatim"
    profile = "default"
    do_thoth = False
    files = []
    for a in argv:
        if a in ("--thoth", "--fix"):
            do_thoth = True
        elif a in ("--full", "--full-verbatim"):
            mode = "full_verbatim"
        elif a.startswith("--mode="):
            mode = a.split("=", 1)[1]
        elif a.startswith("--profile="):
            profile = a.split("=", 1)[1]
        elif a == "--legal":
            profile = "legal"
        elif a == "--list-profiles":
            print("\n  available profiles:")
            for n in names():
                print(f"    {n:<10} {REGISTRY[n].description}")
            print()
            return 0
        else:
            files.append(a)
    if not files:
        print(_USAGE)
        return 2

    path = files[0]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    r = audit_transcript(text, mode=mode, profile=profile)

    print()
    print("  transcript-truth — guideline-compliance receipt")
    print(f"  file: {path}    profile: {profile}    mode: {r.mode}    lines: {r.n_lines}")
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
    if profile in ("legal", "cvl", "transcribeme_legal"):
        print("  NOTE: study/self-check aid. The TranscribeMe exam is no-AI, taken solo —")
        print("        do not use this on actual exam content.")
    print()

    if do_thoth:
        import os
        from .thoth import thoth
        fixed, changes = thoth(text, profile)
        base, ext = os.path.splitext(path)
        out_path = f"{base}.thoth{ext or '.txt'}"
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(fixed + ("\n" if fixed and not fixed.endswith("\n") else ""))
        print("  Thoth — deterministic auto-fix (no model)")
        print("  " + "=" * 60)
        if not changes:
            print("  nothing to fix — already conforms")
        for ln, before, after in changes:
            print(f"  L{ln:<3} {before!r}")
            print(f"       → {after!r}")
        print("  " + "=" * 60)
        after_grade = audit_transcript(fixed, mode=mode, profile=profile).grade
        print(f"  {len(changes)} line(s) fixed   grade {r.grade} → {after_grade}")
        print(f"  wrote: {out_path}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
