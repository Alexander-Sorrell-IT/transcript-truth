"""End-to-end two-layer engine on real audio. claim = FLEURS gold (the submitted
transcript), evidence = an independent Whisper read of the audio. Every flag is
a real divergence; we print the receipt and an honest tally."""
import os, sys, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from itertools import islice
import soundfile as sf
from datasets import load_dataset, Audio
from faster_whisper import WhisperModel
from transcript_truth.verdict import verify

N = int(os.environ.get("N", "12"))
ds = load_dataset("google/fleurs", "ja_jp", split="test", streaming=True).cast_column("audio", Audio(decode=False))
samples = list(islice(ds, N))
m = WhisperModel("medium", device="cpu", compute_type="int8")

def to_wav(ex):
    a = ex["audio"]; raw = a.get("bytes")
    arr, sr = sf.read(io.BytesIO(raw)) if raw else sf.read(a["path"])
    if getattr(arr, "ndim", 1) > 1: arr = arr.mean(axis=1)
    sf.write("/tmp/_clipe.wav", arr, sr)

def hear(path):
    segs, _ = m.transcribe(path, language="ja", task="transcribe")
    return "".join(s.text for s in segs).strip()

tally = {"SOUND": 0, "HOMOPHONE_caught": 0, "AMBIGUOUS": 0}
for k, ex in enumerate(samples):
    to_wav(ex)
    claim = ex["transcription"].strip()      # the submitted transcript
    evidence = hear("/tmp/_clipe.wav")        # independent ASR read of the audio
    flags = verify(claim, evidence)
    print(f"\n===== CLIP {k+1} =====")
    print(f"  submitted: {claim}")
    print(f"  audio says: {evidence}")
    if not flags:
        print("  RECEIPT: clean (claim matches audio)")
    for fl in flags:
        print(f"  [{fl['layer']}/{fl['verdict']}] claim={fl['claim']} | audio={fl['audio']}")
        if fl["layer"] == "SOUND": tally["SOUND"] += 1
        elif fl["verdict"] == "AMBIGUOUS": tally["AMBIGUOUS"] += 1
        else: tally["HOMOPHONE_caught"] += 1

print("\n" + "=" * 70)
print("HONEST TALLY (no Japanese read anywhere -- kana + English glosses only)")
print(f"  Layer-1 SOUND mishearings flagged   : {tally['SOUND']}")
print(f"  Layer-2 HOMOPHONE caught via dict   : {tally['HOMOPHONE_caught']}")
print(f"  Layer-2 AMBIGUOUS (surfaced, human) : {tally['AMBIGUOUS']}")
