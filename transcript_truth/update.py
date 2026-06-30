"""The updater — `get more` for plugins, on a configurable cadence.

`run(force)` is the entry point: if an update is due (per config.frequency: off/hourly/daily/weekly/
monthly) or forced, it fetches the source repo's plugins_manifest.json, diffs it against what's
installed, and reports/pulls newer-or-new plugins (more medical rules, new language plugins…). Data
files (e.g. the medical lists) can be refreshed from their authoritative sources. Mirrors
cli-enforcement's "re-derive from an external source on sync" idea, applied to transcription plugins.
"""
from __future__ import annotations
import base64
import json
import os
import subprocess
import urllib.request

from . import config, manifest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _gh_token():
    """A GitHub token so PRIVATE source repos work: env first, then the gh CLI."""
    for v in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(v):
            return os.environ[v]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def _fetch_file(cfg, path):
    """Fetch a repo file via the authenticated GitHub contents API (works for private + public).
    Returns bytes. Raises on error."""
    u = cfg["update"]
    url = f"https://api.github.com/repos/{u['source']}/contents/{path}?ref={u['branch']}"
    headers = {"User-Agent": "transcript-truth-updater", "Accept": "application/vnd.github.raw+json"}
    tok = _gh_token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as r:
        data = r.read()
    # raw accept header returns the file bytes directly; if JSON (base64) sneaks through, decode it
    try:
        j = json.loads(data)
        if isinstance(j, dict) and j.get("encoding") == "base64":
            return base64.b64decode(j["content"])
    except Exception:
        pass
    return data


def _remote_manifest(cfg):
    return json.loads(_fetch_file(cfg, "plugins_manifest.json"))


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
            try:
                body = _fetch_file(cfg, rel)
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
