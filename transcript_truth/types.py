from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

# Same weighting philosophy as RoboTruth's grade.py.
# "review" = surfaced for human judgment (homophone/colloquial candidates), weight 0 —
# it shows in the receipt but never lowers the deterministic grade on its own.
SEVERITY_WEIGHT = {"critical": 3, "moderate": 1, "minor": 0, "review": 0}


@dataclass
class Flag:
    rule: str                  # which scanner fired
    label: str                 # human-readable violation
    line: int = 0              # cited at line (RoboTruth cites file:line; here it's line)
    severity: str = "moderate"  # critical | moderate | minor
    evidence: str = ""         # the offending text
    fix: str = ""              # guideline-grounded remedy


@dataclass
class Line:
    n: int
    text: str


@dataclass
class Transcript:
    lines: List[Line]
    mode: str = "clean_verbatim"   # clean_verbatim | full_verbatim


@dataclass
class Receipt:
    grade: str                 # A | B | C | D | F
    score: int
    n_critical: int
    n_lines: int
    mode: str
    flags: List[Flag] = field(default_factory=list)
    math: str = ""
