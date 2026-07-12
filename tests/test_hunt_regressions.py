"""Regression pins from the 175-agent adversarial system hunt (2026-07-11/12).
Every case here was a CONFIRMED, double-verified bug — executed repro, skeptic + impact pass."""
import json
import os

import transcript_truth.consensus as C
from transcript_truth import metrics as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_flagship_name_majority_beats_backbone_garble():
    """The 2.6M-name gazetteer must not shield a backbone garble from the family majority
    ('Shevon' backbone vs 2-family 'Siobhan') — this single guard regressed the flagship
    consensus-beats-best-single result for a month."""
    C._reliability_by_lang.cache_clear()
    rows = json.load(open(os.path.join(ROOT, "bench", "live_results.json")))
    row = next(r for r in rows if "Siobhan" in " ".join(r["reads"].values()))
    assert "Siobhan" in C.consensus_tokens(row["reads"], "en")["text"]


def test_flagship_consensus_beats_best_single():
    """PERFECTION_PLAN Phase I, re-pinned on the current ruler: mean consensus WER < mean
    Scribe WER on the English hard clips (recomputed from saved reads — no API)."""
    C._reliability_by_lang.cache_clear()
    rows = json.load(open(os.path.join(ROOT, "bench", "live_results.json")))
    cons, scribe = [], []
    for r in rows:
        ref = json.load(open(os.path.join(ROOT, "bench", "battery", r["case"] + ".json")))["text"]
        cons.append(M.wer(ref, C.consensus_tokens(r["reads"], "en")["text"], lang="en"))
        scribe.append(M.wer(ref, r["reads"]["scribe"], lang="en"))
    assert sum(cons) < sum(scribe)


def test_korean_word_boundaries_survive_the_vote():
    reads = {"a": "안녕하세요 오늘 날씨가 좋네요", "b": "안녕하세요 오늘 날씨가 좋네요"}
    assert C.consensus_tokens(reads, "ko")["text"] == "안녕하세요 오늘 날씨가 좋네요"


def test_japanese_seam_splices_and_dedups():
    """Space-free scripts could NEVER splice (.split() = one token) — every long-audio seam
    duplicated the full overlap, and it survived into final output via the scribe anchor."""
    a = "本日はお集まりいただきありがとうございます最初の議題は予算の見直しです"
    b = "最初の議題は予算の見直しです次に人事の話に移ります"
    out, ok = C._splice(a, b, win=90)
    assert ok and out.count("最初の議題は予算の見直しです") == 1
    # and English splicing is unchanged
    out2, ok2 = C._splice("the meeting covered the budget review in detail today",
                          "budget review in detail today and then personnel matters", win=90)
    assert ok2 and out2.count("budget review in detail today") == 1


def test_ruler_sees_decimal_errors():
    assert M.wer("take 2.5 milligrams", "take 25 milligrams") > 0
    assert M.wer("take 2.5 milligrams", "take 2.5 milligrams") == 0.0
    assert M.wer("cost 47,000,000 dollars", "cost forty seven million dollars") == 0.0
    assert M.wer("es sind 2,5 prozent", "es sind 25 prozent", lang="de") > 0


def test_medical_slash_and_glued_doses_flagged():
    from transcript_truth.medical_rules import dangerous_abbreviations
    from transcript_truth.engine import parse_transcript
    def ev(text, lang="en"):
        t = parse_transcript(text)
        t.lang = lang
        return [f.evidence for f in dangerous_abbreviations(t)]
    assert "U" in ev("insulin 10 U/day")
    assert "MTX" in ev("gave MTX10mg dose")
    assert "MSO4" in ev("gave MSO4 now")
    assert ev("người ưa 10 thuốc", "vi") == []          # Vietnamese 'ưa' stays one run


def test_runner_routes_all_languages():
    from transcript_truth.runner import LANG_PROFILE
    for lang in ("de", "fr", "pt", "tr", "vi", "ko", "ar", "hi", "ur"):
        assert LANG_PROFILE.get(lang) == lang


def test_detect_multi_survives_detector_crash(monkeypatch, tmp_path):
    from transcript_truth import language as L, witness as W
    monkeypatch.setattr(W, "deepgram_detect_language", lambda p: (_ for _ in ()).throw(RuntimeError))
    monkeypatch.setattr(W, "whisper_detect_language", lambda p: "tr")
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF0000WAVE")
    assert L.detect_multi(str(wav))["lang"] == "tr"


def test_mixed_digit_scale_numbers():
    from transcript_truth.numparse import values
    assert dict(values("40 bin lira", "tr")) == {40000: 1}
    assert dict(values("5 million dollars", "en")) == {5000000: 1}
    assert dict(values("dos millones", "es")) == {2000000: 1}
    assert dict(values("zweitausend Euro", "de")) == {2000: 1}


def test_hard_gate_pass_and_review():
    """Phase V: below-floor output carries status='review' mechanically — never silent."""
    agree = {"deepgram": "hello world today", "scribe": "hello world today",
             "gemini": "hello world today"}
    tok = C.consensus_tokens(agree, "en")
    assert C._gate(agree, tok)["status"] == "pass"
    one_family = {"hf": "hello world today", "whisper": "hello world today"}
    assert C._gate(one_family, C.consensus_tokens(one_family, "en"))["status"] == "review"
    chaos = {"deepgram": "aaa bbb ccc", "scribe": "xxx yyy zzz", "gemini": "qqq rrr sss"}
    assert C._gate(chaos, C.consensus_tokens(chaos, "en"))["status"] == "review"


def test_urdu_segmentation_not_word_errors():
    """Clitic spacing is orthography ('کر دیا' == 'کردیا'); real mishearings still count."""
    assert M.wer("کر دیا گیا", "کردیا گیا", lang="ur") == 0.0
    assert M.wer("بچّے بُوڑھے", "بچے بوڑھے", lang="ur") == 0.0
    assert M.wer("حوزات ملی", "حوتات ملی", lang="ur") > 0
