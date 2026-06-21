from __future__ import annotations
from .types import Flag, SEVERITY_WEIGHT

# Pure function, same shape as RoboTruth's grade_and_verdict — no LLM, deterministic.


def grade_and_verdict(flags: list[Flag]) -> tuple[str, int, int, str]:
    n_crit = sum(1 for f in flags if f.severity == "critical")
    n_review = sum(1 for f in flags if f.severity == "review")
    # objective errors (kana-rule violations, non-word mishearings) carry weight and
    # move the grade; "review" items are human-decide -> they cap the grade below A
    # (can't be a clean pass with open questions) but don't crater it.
    score = sum(SEVERITY_WEIGHT.get(f.severity, 0) for f in flags)
    if n_crit >= 2:
        grade = "F"
    elif n_crit == 1:
        grade = "D"
    elif score >= 4:
        grade = "D"
    elif score >= 2:
        grade = "C"
    elif score == 1:
        grade = "B"
    elif n_review > 0:
        grade = "B"          # open human-review items -> not a clean A
    else:
        grade = "A"
    math = f"{grade}: {len(flags)} flags ({n_crit} critical, {n_review} review); score={score}"
    return grade, score, n_crit, math
