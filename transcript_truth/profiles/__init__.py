"""Profile registry with auto-discovery.

Every non-underscore module in this package is imported at load time so each one
self-registers via _base.register(). To add a language/style-guide: create a new
file here that builds a Profile and registers it — it appears in the CLI and in
audit_transcript(profile=...) automatically.
"""
from __future__ import annotations
import importlib
import pkgutil
from ._base import Profile, register, get, names, REGISTRY

# auto-import sibling profile modules so they self-register
for _m in pkgutil.iter_modules(__path__):
    if not _m.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_m.name}")

__all__ = ["Profile", "register", "get", "names", "REGISTRY"]
