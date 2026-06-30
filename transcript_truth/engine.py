from __future__ import annotations
from .types import Transcript, Line, Receipt
from .scanners import run_scanners
from .grade import grade_and_verdict
from .profiles import get as get_profile


def parse_transcript(text: str, mode: str = "clean_verbatim") -> Transcript:
    lines = [Line(i + 1, t) for i, t in enumerate(text.splitlines())]
    return Transcript(lines=lines, mode=mode)


def audit_transcript(text: str, mode: str = "clean_verbatim", coherence: bool = False,
                     profile: str = "default", domain: str | None = None) -> Receipt:
    """Ingest -> deterministic scanners -> pure-function grade. Mirrors RoboTruth.audit_diff.

    profile selects the language/style-guide rule set (see transcript_truth.profiles):
    "default" = Japanese + GoTranscript English (original engine); "legal" =
    TranscribeMe Clean Verbatim for Legal. Each profile is a drop-in plug-in.

    coherence=True adds the opt-in thin-context homophone witness (Qwen blank-fill,
    gated deterministically). It is OFF by default so the default path stays fast and
    model-free; its flags are 'review' tier (surfaced for a human, cap the grade at B,
    never enter the deterministic error score)."""
    if domain and domain != "general":
        from .domains import compose
        prof = compose(profile, domain)     # language × domain = both scanner sets
    else:
        prof = get_profile(profile)
    t = parse_transcript(text, mode)
    flags = run_scanners(t, prof.scanners)
    if coherence:
        from .coherence import coherence_homophones
        from .en_rules import en_homophone_errors
        from .language import segments
        for ln in t.lines:
            # route each language run to its own catalog (and skip cross-language Qwen calls)
            for lang, run in segments(ln.text):
                if not run.strip():
                    continue
                if lang == "ja":
                    for f in coherence_homophones(run):
                        f.line = ln.n; flags.append(f)
                elif lang == "en":
                    for f in en_homophone_errors(run):
                        f.line = ln.n; flags.append(f)
        flags.sort(key=lambda f: (f.line, f.rule))
    grade, score, n_crit, math = grade_and_verdict(flags)
    return Receipt(
        grade=grade, score=score, n_critical=n_crit,
        n_lines=len(t.lines), mode=mode, flags=flags, math=math,
    )
