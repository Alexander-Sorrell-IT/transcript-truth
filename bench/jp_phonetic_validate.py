"""OBJECTIVE validation of the RoboTruth-for-transcription core claim.

Claim under test:  "flag every mishearing whose READING differs from the audio,
deterministically; honestly miss only true identical-reading homophones."

Oracle = FLEURS gold transcript (correct by definition). No Japanese reading
required by a human -- this is string comparison against the label, exactly like
a unit test validates code you can't read by running it against expected output.

For each clip:
  gold (truth)  --Sudachi-->  reading_gold   == what the audio actually says
  whisper (hyp) --Sudachi-->  reading_hyp    == what got written
  diff the surface tokens; for each REPLACED span ask:
     reading differs?  -> CAUGHT  (the deterministic verdict layer fires)
     reading identical? -> MISSED (true homophone -- the stated, honest boundary)
"""
import os, sys, io, difflib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from itertools import islice
import soundfile as sf
from datasets import load_dataset, Audio
from faster_whisper import WhisperModel
from sudachipy import dictionary, tokenizer

N = int(os.environ.get("N", "12"))
_tok = dictionary.Dictionary().create()
_MODE = tokenizer.Tokenizer.SplitMode.C

def toks(s):
    return [m for m in _tok.tokenize(s, _MODE)]

def surf(ms):  # surface forms
    return [m.surface() for m in ms]

def reading(ms):  # katakana reading string per token
    return [m.reading_form() for m in ms]

print("loading real Japanese clips...", flush=True)
ds = load_dataset("google/fleurs", "ja_jp", split="test", streaming=True).cast_column("audio", Audio(decode=False))
samples = list(islice(ds, N))
print(f"got {len(samples)} clips; loading whisper medium...", flush=True)
m = WhisperModel("medium", device="cpu", compute_type="int8")

def to_wav(ex):
    a = ex["audio"]; raw = a.get("bytes")
    arr, sr = sf.read(io.BytesIO(raw)) if raw else sf.read(a["path"])
    if getattr(arr, "ndim", 1) > 1:
        arr = arr.mean(axis=1)
    sf.write("/tmp/_clipv.wav", arr, sr)

def transcribe():
    segs, _ = m.transcribe("/tmp/_clipv.wav", language="ja", task="transcribe")
    return "".join(s.text for s in segs).strip()

# tallies
real_errors = caught = missed_homophone = 0
clip_rows = []

for k, ex in enumerate(samples):
    to_wav(ex)
    gold = ex["transcription"].strip()
    hyp = transcribe()
    gm, hm = toks(gold), toks(hyp)
    gs, hs = surf(gm), surf(hm)
    gr, hr = reading(gm), reading(hm)
    sm = difflib.SequenceMatcher(a=gs, b=hs, autojunk=False)
    clip_caught, clip_missed = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        # span that differs between gold and hyp
        g_surf = "".join(gs[i1:i2]); h_surf = "".join(hs[j1:j2])
        g_read = "".join(gr[i1:i2]); h_read = "".join(hr[j1:j2])
        real_errors += 1
        if g_read != h_read:
            caught += 1
            clip_caught.append(f"{h_surf}[{h_read}] != {g_surf}[{g_read}]")
        else:
            missed_homophone += 1
            clip_missed.append(f"{h_surf} == {g_surf} (reading {g_read})")
    status = "CLEAN" if not (clip_caught or clip_missed) else ""
    clip_rows.append((k+1, gold, hyp, clip_caught, clip_missed, status))

print("\n" + "=" * 70)
for n, gold, hyp, c, miss, st in clip_rows:
    print(f"\n--- CLIP {n} {st}")
    print(f"  TRUTH: {gold}")
    print(f"  HEARD: {hyp}")
    for x in c:
        print(f"   CAUGHT : {x}")
    for x in miss:
        print(f"   MISSED : {x}  <- true homophone, stated boundary")

print("\n" + "=" * 70)
print("OBJECTIVE RESULT (oracle = FLEURS gold, no Japanese reading needed)")
print(f"  real transcription errors (gold vs whisper) : {real_errors}")
print(f"  caught by reading-mismatch (deterministic)  : {caught}")
print(f"  missed = true identical-reading homophones  : {missed_homophone}")
if real_errors:
    print(f"  --> deterministic catch rate                : {caught}/{real_errors} = {100*caught/real_errors:.0f}%")
    print(f"  --> uncatchable-by-design (honest residual) : {missed_homophone}/{real_errors} = {100*missed_homophone/real_errors:.0f}%")
