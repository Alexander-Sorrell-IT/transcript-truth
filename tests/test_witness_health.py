"""Witness-health honesty layer — the anti-silent-death tests (offline, no keys, no network).

The incident being guarded against: the hf key went 402 (credits depleted) and every call
quietly returned "" — Japanese jobs ran 3 ears instead of 4 for weeks and NOTHING said so.
Covers the three pieces:
  HEALTH recording — cloud witnesses classify WHY they died (402 -> OUT OF CREDITS, 401 ->
                     bad key, URLError -> network, missing key -> no API key) as a side
                     channel; return/raise contracts unchanged.
  transcribe/_gate — witness_health is embedded in every result; a DEAD rostered ear
                     forces gate status 'review' with a reason naming witness + HTTP code.
  --ears preflight — all-alive -> exit 0; any dead/empty roster ear -> exit 1, and the
                     dead line carries the recorded reason.
"""
import io, json, os, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from transcript_truth import cli, consensus, witness


@pytest.fixture(autouse=True)
def _fresh_health():
    witness.health_reset()
    yield
    witness.health_reset()


@pytest.fixture
def wav(tmp_path):
    p = tmp_path / "a.wav"
    p.write_bytes(b"RIFF0000WAVEfake")     # witnesses only read bytes; urlopen is stubbed
    return str(p)


class _Resp:
    """Minimal urlopen stand-in: context manager yielding a JSON body file-object."""
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return io.BytesIO(json.dumps(self._payload).encode())

    def __exit__(self, *a):
        return False


def _http_error(code, msg):
    return urllib.error.HTTPError("http://x", code, msg, {}, None)


# ---------- health recording: WHY a cloud witness died ----------

def test_402_records_out_of_credits(monkeypatch, wav):
    monkeypatch.setattr(witness, "_key", lambda n: "k")
    def boom(req, timeout=None):
        raise _http_error(402, "Payment Required")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(urllib.error.HTTPError):        # contract unchanged: still raises
        witness.hf_read(wav, language="ja")
    assert witness.HEALTH["hf"] == {"status": "error", "reason": "HTTP 402 OUT OF CREDITS"}


def test_401_records_bad_key(monkeypatch, wav):
    monkeypatch.setattr(witness, "_key", lambda n: "k")
    def boom(req, timeout=None):
        raise _http_error(401, "Unauthorized")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(urllib.error.HTTPError):
        witness.deepgram_read(wav, language="en")
    assert witness.HEALTH["deepgram"] == {"status": "error", "reason": "HTTP 401 bad key"}


def test_network_error_records_network(monkeypatch, wav):
    monkeypatch.setattr(witness, "_key", lambda n: "k")
    def boom(req, timeout=None):
        raise urllib.error.URLError("dns is down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(urllib.error.URLError):
        witness.deepgram_detect_language(wav)
    assert witness.HEALTH["deepgram_detect_language"] == {"status": "error", "reason": "network"}


def test_missing_key_records_no_api_key(monkeypatch, wav):
    def nokey(name):
        raise RuntimeError(f"{name} not found")        # _key's exact raise shape
    monkeypatch.setattr(witness, "_key", nokey)
    with pytest.raises(RuntimeError):
        witness.hf_read(wav, language="ja")
    assert witness.HEALTH["hf"] == {"status": "error", "reason": "no API key"}


def test_working_read_records_ok(monkeypatch, wav):
    monkeypatch.setattr(witness, "_key", lambda n: "k")
    payload = {"results": {"channels": [{"alternatives": [{"transcript": "hello world"}]}]}}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _Resp(payload))
    assert witness.deepgram_read(wav, language="en") == "hello world"
    assert witness.HEALTH["deepgram"] == {"status": "ok", "reason": ""}


def test_empty_read_records_empty(monkeypatch, wav):
    monkeypatch.setattr(witness, "_key", lambda n: "k")
    payload = {"results": {"channels": [{"alternatives": [{"transcript": ""}]}]}}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _Resp(payload))
    assert witness.deepgram_read(wav, language="en") == ""
    assert witness.HEALTH["deepgram"]["status"] == "empty"


def test_scribe_ok_recorded_under_roster_name(monkeypatch, wav):
    # health keys are ROSTER names ('scribe'), not function names — the gate and the
    # preflight must speak the same vocabulary as consensus.ROSTER
    monkeypatch.setattr(witness, "_key", lambda n: "k")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp({"text": "hi there"}))
    assert witness.elevenlabs_read(wav) == "hi there"
    assert witness.HEALTH["scribe"] == {"status": "ok", "reason": ""}


def test_whisper_local_backend_missing_records_error(monkeypatch, wav):
    # Two distinct dead-ear diagnoses (verifier-found 2026-07-24): the mlx subprocess returns
    # None BOTH when mlx isn't installed and when an installed mlx crashed/timed out — the
    # fixes differ (install vs debug), so the recorded reason must too.
    monkeypatch.setattr(witness, "_mlx_whisper_subprocess", lambda *a, **k: None)
    monkeypatch.setattr(witness, "_WHISPER_LOCAL", None)
    monkeypatch.setitem(sys.modules, "faster_whisper", None)   # import -> ImportError
    monkeypatch.setattr(witness, "_have_mlx", lambda: False)   # nothing installed at all
    assert witness.whisper_local(wav) == ""                    # contract: '' not raise
    h = witness.HEALTH["whisper"]
    assert h["status"] == "error" and "backend not installed" in h["reason"]
    monkeypatch.setattr(witness, "_have_mlx", lambda: True)    # mlx present, its run failed
    assert witness.whisper_local(wav) == ""
    h = witness.HEALTH["whisper"]
    assert h["status"] == "error" and "mlx run failed" in h["reason"]


def test_whisper_local_mlx_success_records_ok(monkeypatch, wav):
    monkeypatch.setattr(witness, "_mlx_whisper_subprocess", lambda *a, **k: "hello from mlx")
    assert witness.whisper_local(wav) == "hello from mlx"
    assert witness.HEALTH["whisper"] == {"status": "ok", "reason": ""}


# ---------- _run_witnesses: leaks are recorded, specifics never clobbered ----------

def test_run_witnesses_records_leaked_exception(monkeypatch):
    def boom(name, path, lang):
        raise ValueError("chunker exploded")
    monkeypatch.setattr(consensus, "_witness_call", boom)
    reads = consensus._run_witnesses(["deepgram"], "x.wav", "en", False, None)
    assert reads["deepgram"] == ""                             # degrade contract unchanged
    h = witness.HEALTH["deepgram"]
    assert h["status"] == "error" and "ValueError" in h["reason"]


def test_run_witnesses_keeps_specific_reason(monkeypatch):
    # the witness's own classification (HTTP 402 OUT OF CREDITS) must survive the
    # catch-all — a bare repr must never overwrite the actionable reason
    def boom(name, path, lang):
        witness._health("hf", "error", "HTTP 402 OUT OF CREDITS")
        raise _http_error(402, "Payment Required")
    monkeypatch.setattr(consensus, "_witness_call", boom)
    consensus._run_witnesses(["hf"], "x.wav", "en", False, None)
    assert witness.HEALTH["hf"]["reason"] == "HTTP 402 OUT OF CREDITS"


# ---------- transcribe: witness_health embedded, dead rostered ear forces review ----------

def _wire_roster(monkeypatch, reads, sick=None):
    """Stub roster_panel (the established pattern from test_two_tier) and record the
    health each witness would have recorded, AFTER transcribe's health_reset runs."""
    def fake_roster(path, lang, seams=None):
        for name, (status, reason) in (sick or {}).items():
            witness._health(name, status, reason)
        for name in reads:
            if name not in (sick or {}):
                witness._health(name, "ok")
        return dict(reads)
    monkeypatch.setattr(consensus, "roster_panel", fake_roster)
    monkeypatch.setattr(consensus, "_stretch", lambda a, r: None)   # no slow-tier files
    monkeypatch.setattr(consensus.os, "remove", lambda p: None)


def test_transcribe_returns_witness_health(monkeypatch):
    _wire_roster(monkeypatch, {"deepgram": "the meeting is at noon",
                               "gemini": "the meeting is at noon"})
    r = consensus.transcribe("x.wav", "en")
    assert r["witness_health"]["deepgram"]["status"] == "ok"
    assert r["witness_health"]["gemini"]["status"] == "ok"
    assert r["gate"]["status"] == "pass"
    assert not any("DEAD" in x for x in r["gate"]["reasons"])


def test_transcribe_dead_roster_witness_forces_review(monkeypatch):
    # survivors AGREE — without the dead-ear check this would present as confident
    _wire_roster(monkeypatch, {"deepgram": "the meeting is at noon",
                               "gemini": "the meeting is at noon"},
                 sick={"hf": ("error", "HTTP 402 OUT OF CREDITS")})
    r = consensus.transcribe("x.wav", "en")
    assert r["witness_health"]["hf"] == {"status": "error", "reason": "HTTP 402 OUT OF CREDITS"}
    assert r["gate"]["status"] == "review"
    assert any("witness hf DEAD" in x and "HTTP 402" in x and "roster not whole" in x
               for x in r["gate"]["reasons"])


def test_transcribe_resets_stale_health(monkeypatch):
    witness._health("hf", "error", "stale from a previous run")
    _wire_roster(monkeypatch, {"deepgram": "the meeting is at noon",
                               "gemini": "the meeting is at noon"})
    r = consensus.transcribe("x.wav", "en")
    assert "hf" not in r["witness_health"]          # health_reset ran — stale entry gone
    assert r["gate"]["status"] == "pass"


# ---------- --ears preflight: exit-code logic + dead-line reason ----------

def test_ears_all_alive_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(consensus, "_witness_call",
                        lambda n, p, l: f"hello this is {n} speaking clearly")
    rc = cli.main(["--ears=en"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "4/4 roster ears alive" in out           # en roster: deepgram scribe hf gemini
    assert "whisper" in out and "extra ear" in out  # whisper dialed too, not counted
    assert "DEAD" not in out


def test_ears_dead_witness_exits_1_with_reason(monkeypatch, capsys):
    def fake(n, p, l):
        if n == "hf":
            witness._health("hf", "error", "HTTP 402 OUT OF CREDITS")
            raise _http_error(402, "Payment Required")
        return f"hello this is {n} speaking clearly"
    monkeypatch.setattr(consensus, "_witness_call", fake)
    rc = cli.main(["--ears=en"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "DEAD" in out and "HTTP 402 OUT OF CREDITS" in out
    assert "3/4 roster ears alive" in out


def test_ears_empty_read_counts_as_dead(monkeypatch, capsys):
    # empty on a REAL speech sample = dead ear (the sample is real speech precisely so
    # empty-on-silence can't masquerade as alive)
    monkeypatch.setattr(consensus, "_witness_call",
                        lambda n, p, l: "" if n == "gemini" else f"read from {n}")
    rc = cli.main(["--ears=en"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "EMPTY" in out and "3/4 roster ears alive" in out


def test_ears_default_lang_is_ja(monkeypatch, capsys):
    monkeypatch.setattr(consensus, "_witness_call", lambda n, p, l: f"read from {n}")
    rc = cli.main(["--ears"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "lang=ja" in out
    assert f"{len(consensus.ROSTER['ja'])}/{len(consensus.ROSTER['ja'])} roster ears alive" in out


def test_ears_unknown_lang_refuses(capsys):
    rc = cli.main(["--ears=zz"])
    assert rc == 2
    assert "no witness roster" in capsys.readouterr().out


# ------------------------------------------- panel-snapshot semantics (verifier-found moderate)
# HEALTH is last-write-wins and transcribe() re-dials ears AFTER the panel (reask tier, tiny
# clips). The gate must judge the PANEL's health snapshot, frozen before reask: a panel error
# later overwritten by a reask "ok" still reviews, and a reask-only failure on a panel-whole
# ear must NOT brand the roster short-handed.
def test_gate_judges_panel_snapshot_not_live_registry():
    from transcript_truth import witness as W
    from transcript_truth.consensus import _gate
    tok = {"text": "hello world", "uncertain_spans": []}
    reads = {"deepgram": "hello world", "scribe": "hello world"}
    # panel snapshot says gemini DIED on the full-file read...
    panel = {"gemini": {"status": "error", "reason": "HTTP 402 OUT OF CREDITS"}}
    # ...but the live registry was later overwritten by a tiny reask success
    W.health_reset(); W._health("gemini", "ok")
    g = _gate(reads, tok, lang="ja", health=panel)
    assert g["status"] == "review" and any("gemini DEAD" in r for r in g["reasons"])
    # converse: reask-only 429 in the live registry, but the panel was whole -> no dead-ear reason
    W.health_reset(); W._health("gemini", "error", "HTTP 429 rate-limited")
    g2 = _gate(reads, tok, lang="ja", health={"gemini": {"status": "ok", "reason": ""}})
    assert not any("DEAD" in r for r in g2["reasons"])
    W.health_reset()
