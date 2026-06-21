"""YOUR loop: hear the audio -> Japanese + English -> understand + verify.

For each REAL Japanese clip, Whisper runs twice on the SAME audio:
  - transcribe -> the Japanese ("what it says")
  - translate  -> the English  ("what it MEANS") — an independent read

The English is the check: if the Japanese transcript's meaning lines up with the
English of the audio, it's right; if it drifts, that's the flag to fix it. This is
how someone who can't read Japanese understands + verifies it.
"""
import os, sys, io
from itertools import islice
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import soundfile as sf
from datasets import load_dataset, Audio
from faster_whisper import WhisperModel

N = int(os.environ.get("N", "6"))
print("loading real Japanese clips...", flush=True)
# decode=False -> we get raw file bytes and decode with soundfile (no torchcodec needed)
ds = load_dataset("google/fleurs", "ja_jp", split="test", streaming=True).cast_column("audio", Audio(decode=False))
samples = list(islice(ds, N))
print(f"got {len(samples)} clips", flush=True)

print("loading whisper medium...", flush=True)
m = WhisperModel("medium", device="cpu", compute_type="int8")


def to_wav(ex):
    a = ex["audio"]
    raw = a.get("bytes")
    arr, sr = sf.read(io.BytesIO(raw)) if raw else sf.read(a["path"])
    if getattr(arr, "ndim", 1) > 1:
        arr = arr.mean(axis=1)
    sf.write("/tmp/_clip2.wav", arr, sr)


def run(task):
    segs, _ = m.transcribe("/tmp/_clip2.wav", language="ja", task=task)
    return "".join(s.text for s in segs).strip()


for k, ex in enumerate(samples):
    to_wav(ex)
    ja = run("transcribe")   # what it says (Japanese)
    en = run("translate")    # what it means (English) — the check
    print(f"\n===== CLIP {k+1} =====", flush=True)
    print(f"  HEARD (JA) : {ja}")
    print(f"  MEANS (EN) : {en}")
    print(f"  TRUTH (JA) : {ex['transcription']}")
