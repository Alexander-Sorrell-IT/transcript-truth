"""Phase H — wire multi-model consensus into runner (MODEL_MAP.md Stage H, the headline).

Deepgram supplies timestamps + speaker turns (structural backbone); the multi-model consensus
supplies the WORDS. So the end-to-end path is no longer single-model. Consensus injected; the
Deepgram structure stubbed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth import runner


def _dg(monkeypatch, utts):
    monkeypatch.setattr(runner.witness, "deepgram_structured", lambda path, lang: utts)


def test_consensus_words_replace_deepgram_words_keeping_structure(monkeypatch, tmp_path):
    fake = str(tmp_path / "a.wav"); open(fake, "wb").write(b"x")
    _dg(monkeypatch, [
        {"start": 0.0, "end": 2.0, "speaker": 0, "text": "the drug is lisinapril"},   # dg misheard
        {"start": 2.0, "end": 4.0, "speaker": 1, "text": "take it daily"},
    ])
    # multi-model consensus corrected the drug name
    res = runner.transcribe(fake, "en", consensus_fn=lambda: "the drug is lisinopril take it daily")
    assert res["multi_model"] is True
    # corrected word present; deepgram's misheard word gone
    assert "lisinopril" in res["content"] and "lisinapril" not in res["content"]
    # structure preserved: two utterances, original timestamps + speakers
    assert "[00:00] Speaker 1:" in res["transcript"] and "[00:02] Speaker 2:" in res["transcript"]
    assert res["n_utterances"] == 2


def test_empty_consensus_falls_back_to_deepgram(monkeypatch, tmp_path):
    fake = str(tmp_path / "a.wav"); open(fake, "wb").write(b"x")
    _dg(monkeypatch, [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "deepgram text stands"}])
    res = runner.transcribe(fake, "en", consensus_fn=lambda: "")   # no keys / offline
    assert res["content"] == "deepgram text stands"                # graceful single-model fallback


def test_redistribute_keeps_words_within_owning_utterance():
    utts = [{"start": 0.0, "end": 1.0, "speaker": 0, "text": "alpha bravo"},
            {"start": 1.0, "end": 2.0, "speaker": 1, "text": "charlie delta"}]
    out = runner._redistribute(utts, "alpha bravo charlie echo")   # 'delta'->'echo' in utt 2
    assert out[0]["text"] == "alpha bravo"
    assert out[1]["text"] == "charlie echo"
    assert out[0]["speaker"] == 0 and out[1]["start"] == 1.0        # structure intact
