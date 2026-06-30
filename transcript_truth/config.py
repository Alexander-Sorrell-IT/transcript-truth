"""User config for transcript-truth — chiefly the auto-update cadence.

Stored as JSON at ~/.config/transcript-truth/config.json (override with TT_CONFIG). Edit it by
hand or via the CLI (`--set-update-frequency weekly`). The updater (update.py) reads `frequency`
and `last_check` to decide whether an update is due.
"""
from __future__ import annotations
import json
import os
import time

FREQUENCIES = {"off": None, "hourly": 3600, "daily": 86400, "weekly": 604800, "monthly": 2592000}

DEFAULT = {
    "update": {
        "frequency": "weekly",                                  # off|hourly|daily|weekly|monthly
        "source": "alexander-sorrell-it/transcript-truth",      # GitHub repo holding the plugin manifest
        "branch": "main",
        "last_check": None,                                     # epoch seconds of last successful check
        "auto": True,                                          # allow auto-update when due
    }
}


def _path():
    return os.environ.get("TT_CONFIG") or os.path.expanduser("~/.config/transcript-truth/config.json")


def load():
    p = _path()
    cfg = {k: dict(v) for k, v in DEFAULT.items()}
    if os.path.exists(p):
        try:
            disk = json.load(open(p, encoding="utf-8"))
            for k, v in disk.items():
                cfg.setdefault(k, {}).update(v) if isinstance(v, dict) else cfg.__setitem__(k, v)
        except Exception:
            pass
    return cfg


def save(cfg):
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(cfg, open(p, "w", encoding="utf-8"), indent=2)
    return p


def set_update_frequency(freq):
    if freq not in FREQUENCIES:
        raise ValueError(f"frequency must be one of: {', '.join(FREQUENCIES)}")
    cfg = load()
    cfg["update"]["frequency"] = freq
    return save(cfg)


def update_due(cfg=None, now=None):
    """True if an update check is due per the configured cadence."""
    cfg = cfg or load()
    u = cfg.get("update", {})
    interval = FREQUENCIES.get(u.get("frequency", "weekly"))
    if interval is None:                      # 'off'
        return False
    last = u.get("last_check")
    if not last:
        return True
    return (now or time.time()) - last >= interval


def mark_checked(now=None):
    cfg = load()
    cfg["update"]["last_check"] = now or time.time()
    save(cfg)
    return cfg
