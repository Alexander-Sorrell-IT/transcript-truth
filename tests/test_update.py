"""The plugin updater (update.py) — version-diff + cadence logic, network STUBBED.

check() compares the remote manifest to what's installed and sorts plugins into
'updates' (newer version) vs 'new' (not installed). apply() downloads files. run()
gates on the configured cadence. All network calls are stubbed so these are pure/offline.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_truth import update
from transcript_truth.update import _vt, check, apply, run


_CFG = {"update": {"source": "owner/repo", "branch": "main", "frequency": "weekly", "auto": True}}


# ---------- version tuple ----------

def test_vt_parses_dotted_version():
    assert _vt("1.2.3") == (1, 2, 3)


def test_vt_orders_numerically_not_lexically():
    assert _vt("1.10") > _vt("1.9")   # lexical string compare would get this wrong


# ---------- check(): the diff ----------

def _stub_remote(monkeypatch, remote_plugins):
    monkeypatch.setattr(update, "_remote_manifest", lambda cfg: {"plugins": remote_plugins})


def _stub_local(monkeypatch, local_plugins):
    monkeypatch.setattr(update.manifest, "local_manifest", lambda: {"plugins": local_plugins})


def test_check_flags_new_plugin(monkeypatch):
    _stub_local(monkeypatch, {"en": "1.0"})
    _stub_remote(monkeypatch, {"en": "1.0", "ko": "1.0"})   # ko not installed
    res = check(_CFG)
    assert res["error"] is None
    assert "ko" in res["new"] and "ko" not in res["updates"]


def test_check_flags_version_upgrade(monkeypatch):
    _stub_local(monkeypatch, {"en": "1.0"})
    _stub_remote(monkeypatch, {"en": "1.2"})
    res = check(_CFG)
    assert res["updates"]["en"] == ("1.0", "1.2")


def test_check_ignores_same_or_older(monkeypatch):
    _stub_local(monkeypatch, {"en": "2.0"})
    _stub_remote(monkeypatch, {"en": "2.0"})
    res = check(_CFG)
    assert res["updates"] == {} and res["new"] == {}


def test_check_unreachable_source_returns_error(monkeypatch):
    _stub_local(monkeypatch, {"en": "1.0"})
    def boom(cfg):
        raise OSError("no network")
    monkeypatch.setattr(update, "_remote_manifest", boom)
    res = check(_CFG)
    assert res["error"] and "unreachable" in res["error"]
    assert res["updates"] == {} and res["new"] == {}


# ---------- apply(): download + install ----------

def test_apply_writes_fetched_files(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "_ROOT", str(tmp_path))
    monkeypatch.setattr(update, "_remote_manifest",
                        lambda cfg: {"detail": {"ko": {"files": ["transcript_truth/ko_rules.py"]}}})
    monkeypatch.setattr(update, "_fetch_file", lambda cfg, rel: b"# new ko rules\n")
    res = apply(["ko"], _CFG)
    assert res["error"] is None
    assert "transcript_truth/ko_rules.py" in res["written"]
    assert (tmp_path / "transcript_truth" / "ko_rules.py").read_bytes() == b"# new ko rules\n"


# ---------- run(): cadence gate ----------

def test_run_skips_when_not_due(monkeypatch):
    monkeypatch.setattr(update.config, "load", lambda: _CFG)
    monkeypatch.setattr(update.config, "update_due", lambda cfg: False)
    res = run(force=False)
    assert res["ran"] is False and "not due" in res["reason"]


def test_run_force_ignores_schedule(monkeypatch):
    monkeypatch.setattr(update.config, "load", lambda: _CFG)
    monkeypatch.setattr(update.config, "update_due", lambda cfg: False)
    monkeypatch.setattr(update.config, "mark_checked", lambda: None)
    monkeypatch.setattr(update, "check",
                        lambda cfg: {"updates": {}, "new": {}, "error": None})
    res = run(force=True)
    assert res["ran"] is True and res["error"] is None
