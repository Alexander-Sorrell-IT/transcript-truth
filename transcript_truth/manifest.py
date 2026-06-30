"""Plugin manifest — the registry of installed language/domain plugins and their versions.

`plugins_manifest.json` (written by `write_manifest()`) is what the updater compares against the
SAME file published in the source repo: a plugin whose remote version is higher (or that isn't
installed at all) is an available update. This is how `update` knows it can "get more medical" or
new language plugins.
"""
from __future__ import annotations
import json
import os

ENGINE_VERSION = "0.2.0"

# plugin name -> {version, kind, files: [repo-relative paths], data: [refreshable data files]}
PLUGINS = {
    # languages
    "fr": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/fr.py", "transcript_truth/fr_rules.py"]},
    "de": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/de.py", "transcript_truth/de_rules.py"]},
    "pt": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/pt.py", "transcript_truth/pt_rules.py"]},
    "tr": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/tr.py", "transcript_truth/tr_rules.py"]},
    "ko": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/ko.py", "transcript_truth/ko_rules.py"]},
    "vi": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/vi.py", "transcript_truth/vi_rules.py"]},
    "ar": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/ar.py", "transcript_truth/script_rules.py"]},
    "hi": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/hi.py", "transcript_truth/script_rules.py"]},
    "ur": {"version": "1.0.0", "kind": "language", "files": ["transcript_truth/profiles/ur.py", "transcript_truth/script_rules.py"]},
    # domains
    "medical": {"version": "1.0.0", "kind": "domain",
                "files": ["transcript_truth/medical_rules.py"],
                "data_sources": {
                    "dangerous_abbreviations": "ISMP 'Do Not Use' list",
                    "drug_names": "RxNorm (NLM)",
                }},
}


def local_manifest():
    return {"engine": ENGINE_VERSION, "plugins": {n: p["version"] for n, p in PLUGINS.items()},
            "detail": PLUGINS}


def write_manifest(path=None):
    """Write plugins_manifest.json (publish this to the source repo so `update` can compare)."""
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "plugins_manifest.json")
    json.dump(local_manifest(), open(path, "w", encoding="utf-8"), indent=2)
    return path
