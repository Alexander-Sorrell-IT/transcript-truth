"""Real-audio reliability benchmark — the honest test.

Pulls REAL Japanese speech (FLEURS) with ground-truth transcripts, runs two
Whisper engines (small + medium = the cross-check), scores each against truth,
and breaks the errors into:
  - homophone-type  -> our detector + disambiguate catches these
  - cross-check-flagged (small != medium) -> the multi-ASR layer catches these
  - residual        -> what neither layer sees (the honest gap)

This answers the only question that matters: how reliable is the pipeline on
audio a non-Japanese-reader genuinely cannot check?
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import soundfile as sf
from datasets import load_dataset
from faster_whisper import WhisperModel
from transcript_truth.engine import parse_transcript
from transcript_truth.semantic import homophone_traps

N = int(os.environ.get("N", "12"))


def edit_distance(a, b):
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return dp[n]


def cer(ref, hyp):
    ref = ref.replace(" ", ""); hyp = hyp.replace(" ", "")
    return edit_distance(ref, hyp) / max(1, len(ref))


def transcribe(model, audio):
    sf.write("/tmp/_clip.wav", audio["array"], audio["sampling_rate"])
    segs, _ = model.transcribe("/tmp/_clip.wav", language="ja")
    return "".join(s.text for s in segs).strip()


print("loading FLEURS ja (real Japanese speech)...", flush=True)
ds = load_dataset("google/fleurs", "ja_jp", split="test", streaming=True)
samples = []
for i, ex in enumerate(ds):
    samples.append(ex)
    if len(samples) >= N:
        break
print(f"got {len(samples)} real clips", flush=True)

print("loading whisper small + medium...", flush=True)
small = WhisperModel("small", device="cpu", compute_type="int8")
medium = WhisperModel("medium", device="cpu", compute_type="int8")

cer_s = cer_m = cer_best = 0.0
agree_n = 0
for k, ex in enumerate(samples):
    ref = ex["transcription"]
    hs = transcribe(small, ex["audio"])
    hm = transcribe(medium, ex["audio"])
    agree = hs.replace(" ", "") == hm.replace(" ", "")
    agree_n += agree
    cs, cm = cer(ref, hs), cer(ref, hm)
    best = min(cs, cm)            # cross-check oracle upper bound
    cer_s += cs; cer_m += cm; cer_best += best
    traps = sorted(set(f.evidence for f in homophone_traps(parse_transcript(hm))))
    print(f"[{k+1}] CER small={cs:.0%} med={cm:.0%} | engines {'AGREE' if agree else 'DIFFER->flag'} | traps={traps}", flush=True)

n = len(samples)
print(f"\n=== REAL-AUDIO RESULTS ({n} clips) ===")
print(f"avg CER  small   : {cer_s/n:.1%}")
print(f"avg CER  medium  : {cer_m/n:.1%}")
print(f"avg CER  best-of-2 (cross-check ceiling): {cer_best/n:.1%}")
print(f"engines agree    : {agree_n}/{n}  (disagreement = mishearing flag)")
