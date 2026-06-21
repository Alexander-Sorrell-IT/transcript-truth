"""Profile = one (language + style-guide) plug-in.

A profile bundles the scanner functions that apply to a given guideline and the
modes it supports. Profiles self-register by calling `register(...)` at import
time; the package __init__ auto-imports every sibling module, so adding a new
language is literally: drop a file in profiles/ that builds a Profile and calls
register(). Nothing else in the engine needs to change.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple
from ..types import Flag, Transcript

Scanner = Callable[[Transcript], List[Flag]]


@dataclass(frozen=True)
class Profile:
    name: str                              # registry key, e.g. "legal"
    description: str                       # one line, shown by `--list-profiles`
    scanners: Tuple[Scanner, ...]          # the deterministic rule set
    modes: Tuple[str, ...] = ("clean_verbatim", "full_verbatim")
    default_mode: str = "clean_verbatim"
    aliases: Tuple[str, ...] = ()          # alternate registry keys
    fixers: Tuple = ()                      # Thoth auto-fix set: (compiled_pattern, repl) pairs


REGISTRY: Dict[str, Profile] = {}


def register(p: Profile) -> Profile:
    for key in (p.name, *p.aliases):
        REGISTRY[key] = p
    return p


def get(name: str) -> Profile:
    if name not in REGISTRY:
        avail = ", ".join(sorted({p.name for p in REGISTRY.values()}))
        raise KeyError(f"unknown profile {name!r}; available: {avail}")
    return REGISTRY[name]


def names() -> List[str]:
    return sorted({p.name for p in REGISTRY.values()})
