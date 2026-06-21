"""Build a local Japanese sound library: download clean speech clips (audio + gold
transcript) and save them to data/sounds/ so the precision/recall tests have many
real clips to run on, not just the 12 we'd been reusing.

Source: FLEURS ja_jp (open). Saves <clip>.wav + <clip>.txt pairs.
"""
import os, sys, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from itertools import islice
import soundfile as sf
from datasets import load_dataset, Audio

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(DIR, "data", "sounds")
os.makedirs(OUT, exist_ok=True)
N = int(os.environ.get("N", "80"))

print(f"downloading {N} Japanese speech clips -> {OUT}", flush=True)
# train split = clips we have NOT used in the test benchmarks (avoids overlap)
ds = load_dataset("google/fleurs", "ja_jp", split="train", streaming=True).cast_column("audio", Audio(decode=False))
saved = 0
for ex in islice(ds, N):
    a = ex["audio"]; raw = a.get("bytes")
    arr, sr = sf.read(io.BytesIO(raw)) if raw else sf.read(a["path"])
    if getattr(arr, "ndim", 1) > 1:
        arr = arr.mean(axis=1)
    base = os.path.join(OUT, f"clip_{saved:03d}")
    sf.write(base + ".wav", arr, sr)
    open(base + ".txt", "w", encoding="utf-8").write(ex["transcription"].strip())
    saved += 1
    if saved % 20 == 0:
        print(f"  {saved} clips saved", flush=True)
print(f"DONE: {saved} clips (wav+txt) in {OUT}", flush=True)
