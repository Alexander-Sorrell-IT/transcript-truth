from __future__ import annotations
import sys
from .engine import audit_transcript
from .profiles import REGISTRY, names

_SEV = {"critical": "CRIT", "moderate": "WARN", "minor": "minor", "review": "check"}

_USAGE = ("usage: python -m transcript_truth.cli <file.txt> [--profile=legal] [--full] [--thoth]\n"
          "       python -m transcript_truth.cli --list-profiles\n"
          "  --thoth   apply deterministic auto-fixes -> writes <file>.thoth.txt")


def _print_translation_receipt(path, r) -> None:
    """Render the deterministic translation verdict (translate.translate() dict). Surfaces the
    primary text, the FLAGGED/ship-for-review status, the specific failed checks, AND the
    verifiability booleans — an UNVERIFIABLE check is shown as uncertain, never a silent green."""
    checks = r.get("checks")
    nv = checks.get("numbers_verifiable") if checks else None
    xv = checks.get("names_verifiable") if checks else None
    print()
    print("  transcript-truth — translation receipt")
    print(f"  file: {path}    {r.get('src_lang')} -> {r.get('tgt_lang')}")
    print("  " + "=" * 60)
    print("  TRANSLATION:")
    print(f"    {r['text']}" if r.get("text") else "    (no translation produced)")
    print("  " + "-" * 60)
    if r.get("flagged"):
        print("  ⚠ FLAGGED — ship for human review (see below)")
    elif checks and nv and xv:
        print("  ✓ confident — passed the deterministic checks")
    else:
        # not flagged, but the mechanical checks could NOT all run — do not claim they passed.
        # The confidence here is the cross-witness agreement control, not a verified check.
        print("  ✓ not flagged — cleared by cross-witness agreement "
              "(some checks unverifiable; see below)")
    print(f"  cross-witness agreement: {r.get('agreement')}")

    if not checks:
        print("  checks: none — no witness produced output (lone/empty)")
    else:
        nv = checks.get("numbers_verifiable")
        xv = checks.get("names_verifiable")
        print(f"  numbers verifiable: {nv}    names verifiable: {xv}")
        if checks.get("missing_numbers"):
            print(f"    ✗ dropped numbers:    {', '.join(map(str, checks['missing_numbers']))}")
        if checks.get("introduced_numbers"):
            print(f"    ✗ introduced numbers: {', '.join(map(str, checks['introduced_numbers']))}")
        if checks.get("missing_names"):
            print(f"    ✗ dropped names:      {', '.join(map(str, checks['missing_names']))}")
        # the 'review' surface: what could NOT be mechanically verified (uncertainty, not a pass)
        if nv is False:
            print("    ? numbers NOT mechanically verifiable for this language pair "
                  "(spelled-number support missing) — review")
        if xv is False:
            print("    ? names NOT mechanically verifiable (non-Latin source, no reliable "
                  "transliterator) — review")
        if checks.get("ok") and nv and xv and not r.get("flagged"):
            print("    ✓ all numbers and names survived translation")
    print("  " + "=" * 60)
    print("  No model in the verdict path — every flag is a deterministic rule hit.")
    print()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "clean_verbatim"
    profile = "default"
    domain = None
    site = None
    do_thoth = False
    translate_to = None          # Phase 8: --translate=<tgt> switches to the translation track
    src_lang = None              # optional --src=<lang>; else language-valued --profile or auto-detect
    files = []
    for a in argv:
        if a == "--update":                       # cadence-aware: pull newer/new plugins now
            from . import update
            r = update.run(force=True)
            print("update:", r["error"] if r.get("error") else
                  f"{len(r.get('updates',{}))} updated, {len(r.get('new',{}))} new; "
                  f"applied {len(r.get('applied',[]))} files")
            return 0
        elif a == "--refresh-data":               # re-pull domain reference data (RxNorm drugs, …)
            from . import update
            print("refresh-data:", update.refresh_data())
            return 0
        elif a == "--update-check":
            from . import update
            r = update.check()
            print("update check:", r["error"] or
                  f"{len(r['updates'])} updates, {len(r['new'])} new plugins available")
            return 0
        elif a.startswith("--set-update-frequency="):
            from . import config
            try:
                p = config.set_update_frequency(a.split("=", 1)[1])
                print(f"update frequency set ({p})")
            except ValueError as e:
                print(e)
            return 0
        elif a == "--update-status":
            from . import config
            c = config.load()["update"]
            print(f"frequency={c['frequency']} source={c['source']} last_check={c['last_check']} due={config.update_due()}")
            return 0
        elif a.startswith("--domain="):
            domain = a.split("=", 1)[1]
        elif a.startswith("--site="):
            site = a.split("=", 1)[1]
        elif a.startswith("--translate="):          # value form (matches every other value-flag)
            translate_to = a.split("=", 1)[1] or "en"
        elif a == "--translate":                     # bare form -> default target English
            translate_to = "en"
        elif a.startswith("--src="):
            src_lang = a.split("=", 1)[1]
        elif a in ("--thoth", "--fix"):
            do_thoth = True
        elif a in ("--full", "--full-verbatim"):
            mode = "full_verbatim"
        elif a.startswith("--mode="):
            mode = a.split("=", 1)[1]
        elif a.startswith("--profile="):
            profile = a.split("=", 1)[1]
        elif a == "--legal":
            profile = "legal"
        elif a == "--ccsl":
            profile = "ccsl"
        elif a == "--list-profiles":
            print("\n  available profiles:")
            for n in names():
                print(f"    {n:<10} {REGISTRY[n].description}")
            print()
            return 0
        elif a == "--coverage":
            from .domains import coverage_report
            from .manifest import manifest_gaps
            print("\n  language × layer coverage (full = per-language layer; core = universal core only):")
            cur = None
            for row in coverage_report():
                if row["language"] != cur:
                    cur = row["language"]
                    print(f"\n    {cur}:")
                mark = "✓ full" if row["coverage"] == "full" else "· core"
                print(f"      {row['layer']:<12} [{row['kind']:<5}] {mark}")
            gaps = manifest_gaps()
            if any(gaps.values()):
                print(f"\n  manifest drift (registered but not shippable via update):")
                for k in ("languages", "domains", "sites"):
                    if gaps.get(k):
                        print(f"    {k+':':<11} {', '.join(gaps[k])}")
            print()
            return 0
        else:
            files.append(a)
    if not files:
        print(_USAGE)
        return 2

    path = files[0]

    if translate_to:
        # TRANSLATION TRACK (additive; returns before the audit path). files[0] is an AUDIO path,
        # not a text file, so it must NOT reach the open().read() below.
        from .translate import translate as _translate      # lazy: keep `import cli` light + race-free
        # source language: explicit --src, else a language-valued --profile, else auto-detect.
        # `profile` defaults to "default" (NOT a language) — never pass that as a source language.
        src = src_lang or (profile if profile != "default" else None)
        if src is None:
            from . import language                          # detect/route via the ASR detectors
            src = language.detect(path)
        r = _translate(path, src, tgt_lang=translate_to)
        _print_translation_receipt(path, r)
        return 0

    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    r = audit_transcript(text, mode=mode, profile=profile, domain=domain, site=site)

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
        # apply the SAME plug that graded: a composed language×field×site profile carries the
        # layers' Redline fixers (e.g. en+legal+transcribeme → CVL autofix), so pass the composed object.
        if (domain and domain != "general") or (site and site != "general"):
            from .domains import compose
            fix_profile = compose(profile, domain, site)
        else:
            fix_profile = profile
        fixed, changes = thoth(text, fix_profile)
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
        after_grade = audit_transcript(fixed, mode=mode, profile=profile, domain=domain, site=site).grade
        print(f"  {len(changes)} line(s) fixed   grade {r.grade} → {after_grade}")
        print(f"  wrote: {out_path}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
