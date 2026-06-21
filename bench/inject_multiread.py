"""Multi-read catch-rate test. The fix: bring back the AUDIO as the anchor read.

A Japanese word in TEXT fans out to many homophones; the AUDIO heard in context
flattens it to one. So we don't rely on text alone. For each clip we inject a known
same-reading homophone error into the transcript, then check it against THREE
independent witnesses:
  1. Whisper on the real AUDIO   (anchor — context-flattened to the true word)
  2. Qwen correcting the text    (fluent second read)
  3. our deterministic scanners  (dictionary / kana / context)
An injected error is CAUGHT if ANY witness disagrees with it. It survives only if it
fooled all three identically.
"""
import sys, os, glob, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import soundfile as sf
from faster_whisper import WhisperModel
from transcript_truth.verdict import _toks
from transcript_truth.collocation import _homophones, _kata2hira
from transcript_truth.worker import correct_transcript
from transcript_truth.engine import audit_transcript

H = _homophones()
N = int(os.environ.get("N", "20"))
DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = WhisperModel("medium", device="cpu", compute_type="int8")

def whisper_read(wav):
    segs, _ = m.transcribe(wav, language="ja", task="transcribe")
    return "".join(s.text for s in segs)

by_whisper = by_qwen = by_auditor = miss = total = 0
miss_ex = []
for txt_f in sorted(glob.glob(os.path.join(DIR, "data", "sounds", "*.txt"))):
    if total >= N:
        break
    wav_f = txt_f[:-4] + ".wav"
    if not os.path.exists(wav_f):
        continue
    gold = open(txt_f, encoding="utf-8").read().strip()
    inj = None
    for mo in _toks(gold):
        s = mo.surface()
        if len(s) < 2:
            continue
        cands = [c["word"] for c in H.get(_kata2hira(mo.reading_form()), []) if c["word"] != s]
        if cands:
            inj = (s, cands[0]); break
    if not inj:
        continue
    true_w, wrong_w = inj
    errored = gold.replace(true_w, wrong_w, 1)
    total += 1
    # 3 independent witnesses
    wr = whisper_read(wav_f)
    try:
        qr = correct_transcript(errored)
    except Exception:
        qr = errored
    flags = audit_transcript(errored).flags
    aud_hit = any(wrong_w in (f.evidence or "") or wrong_w in (f.label or "") for f in flags)

    if wrong_w not in wr:            # audio anchor disagrees (true word in the sound+context)
        by_whisper += 1; who = "WHISPER-AUDIO"
    elif wrong_w not in qr:          # Qwen fixed it
        by_qwen += 1; who = "QWEN"
    elif aud_hit:                    # deterministic scan caught it
        by_auditor += 1; who = "AUDITOR"
    else:
        miss += 1; who = "MISS"; miss_ex.append(f"{true_w}->{wrong_w}")
    print(f"[{total}] {true_w}->{wrong_w} : {who}", flush=True)

caught = by_whisper + by_qwen + by_auditor
print("\n" + "=" * 60)
print(f"injected errors: {total}")
print(f"  caught by WHISPER-AUDIO anchor : {by_whisper}")
print(f"  caught by QWEN                 : {by_qwen}")
print(f"  caught by deterministic AUDITOR: {by_auditor}")
print(f"  MISSED by all three            : {miss}")
print(f"  => multi-read catch rate: {caught}/{total} = {100*caught//max(total,1)}%")
if miss_ex:
    print("  misses:", miss_ex)
