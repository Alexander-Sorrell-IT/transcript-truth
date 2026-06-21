"""transcript-truth — deterministic transcription-guideline auditor.

Forked from RoboTruth's "no model in the verdict path" engine: heuristic-free
scanners read a transcript, a pure-function grader emits the verdict, and every
flag is cited at its line. The LLM (which was confidently wrong on our quiz) is
nowhere near the verdict — only deterministic rule hits are.
"""
from .engine import audit_transcript, parse_transcript
from .types import Flag, Receipt, Transcript

__all__ = ["audit_transcript", "parse_transcript", "Flag", "Receipt", "Transcript"]
