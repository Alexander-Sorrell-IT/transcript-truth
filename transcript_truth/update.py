"""The updater — `get more` for plugins, on a configurable cadence.

`run(force)` is the entry point: if an update is due (per config.frequency: off/hourly/daily/weekly/
monthly) or forced, it fetches the source repo's plugins_manifest.json, diffs it against what's
installed, and reports/pulls newer-or-new plugins (more medical rules, new language plugins…). Data
files (e.g. the medical lists) can be refreshed from their authoritative sources. Mirrors
cli-enforcement's "re-derive from an external source on sync" idea, applied to transcription plugins.
"""
from __future__ import annotations
import json
import os
import urllib.request

from . import config, manifest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _remote_manifest(cfg):
    u = cfg["update"]
    url = f"https://raw.githubusercontent.com/{u['source']}/{u['branch']}/plugins_manifest.json"
    req = urllib.request.Request(url, headers={"User-Agent": "transcript-truth-updater"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _vt(v):
    return tuple(int(x) for x in str(v).split(".") if x.isdigit())


def check(cfg=None):
    """Compare the source repo's manifest to what's installed. Returns
    {updates: {name: (local, remote)}, new: {name: remote}, error: str|None}."""
    cfg = cfg or config.load()
    local = manifest.local_manifest()["plugins"]
    try:
        remote = _remote_manifest(cfg).get("plugins", {})
    except Exception as e:
        return {"updates": {}, "new": {}, "error": f"source unreachable ({str(e)[:60]}) — "
                f"publish plugins_manifest.json to {cfg['update']['source']} to enable updates"}
    updates, new = {}, {}
    for name, rv in remote.items():
        if name not in local:
            new[name] = rv
        elif _vt(rv) > _vt(local[name]):
            updates[name] = (local[name], rv)
    return {"updates": updates, "new": new, "error": None}


def apply(names, cfg=None):
    """Download the listed plugins' files from the source repo and install them. Returns paths written."""
    cfg = cfg or config.load()
    u = cfg["update"]
    try:
        detail = _remote_manifest(cfg).get("detail", {})
    except Exception as e:
        return {"error": str(e)[:80], "written": []}
    written = []
    for name in names:
        for rel in detail.get(name, {}).get("files", []):
            url = f"https://raw.githubusercontent.com/{u['source']}/{u['branch']}/{rel}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "transcript-truth-updater"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read()
                dest = os.path.join(_ROOT, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                open(dest, "wb").write(body)
                written.append(rel)
            except Exception:
                pass
    return {"error": None, "written": written}


def run(force=False, auto_apply=None):
    """Cadence-aware update. Returns a summary dict. `force` ignores the schedule."""
    cfg = config.load()
    if not force and not config.update_due(cfg):
        return {"ran": False, "reason": f"not due (frequency={cfg['update']['frequency']})"}
    res = check(cfg)
    config.mark_checked()
    auto = cfg["update"].get("auto", True) if auto_apply is None else auto_apply
    applied = {"written": []}
    if auto and (res["updates"] or res["new"]) and not res["error"]:
        applied = apply(list(res["updates"]) + list(res["new"]), cfg)
    return {"ran": True, "error": res["error"], "updates": res["updates"],
            "new": res["new"], "applied": applied.get("written", [])}
