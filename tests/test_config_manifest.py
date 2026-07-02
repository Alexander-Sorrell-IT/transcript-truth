"""Phase 2 — config (update cadence + persistence) and manifest (plugin registry).
config uses a temp file via the TT_CONFIG env override, so nothing touches the real ~/.config.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_truth import config, manifest


# ---------- config.py ----------

def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("TT_CONFIG", str(tmp_path / "config.json"))


def test_load_defaults_when_no_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    cfg = config.load()
    assert cfg["update"]["frequency"] == "weekly"


def test_save_then_load_roundtrip(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    cfg = config.load()
    cfg["update"]["branch"] = "custom-branch"
    config.save(cfg)
    assert config.load()["update"]["branch"] == "custom-branch"


def test_set_frequency_rejects_bad_value(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    try:
        config.set_update_frequency("yearly")
        assert False, "should have raised"
    except ValueError:
        pass


def test_update_due_false_when_off(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert config.update_due({"update": {"frequency": "off"}}) is False


def test_update_due_true_when_never_checked(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    assert config.update_due({"update": {"frequency": "daily", "last_check": None}}) is True


def test_update_due_respects_interval(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    cfg = {"update": {"frequency": "daily", "last_check": 1000.0}}
    assert config.update_due(cfg, now=1000.0 + 3600) is False       # 1h < 1 day
    assert config.update_due(cfg, now=1000.0 + 90000) is True        # >1 day


def test_mark_checked_persists_timestamp(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    config.mark_checked(now=12345.0)
    assert config.load()["update"]["last_check"] == 12345.0


# ---------- manifest.py ----------

def test_local_manifest_versions_match_detail():
    m = manifest.local_manifest()
    for name, ver in m["plugins"].items():
        assert m["detail"][name]["version"] == ver


def test_write_manifest_to_temp(tmp_path):
    p = manifest.write_manifest(str(tmp_path / "plugins_manifest.json"))
    data = json.load(open(p))
    assert data["engine"] == manifest.ENGINE_VERSION and "legal" in data["plugins"]


def test_manifest_gaps_shape():
    gaps = manifest.manifest_gaps()
    assert set(gaps) == {"languages", "domains", "sites"}
    assert "general" not in gaps["domains"]   # 'general' is not a shippable plugin
