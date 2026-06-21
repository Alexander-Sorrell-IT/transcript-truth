"""Mine an EMPIRICAL ASR-confusion table from real Whisper output. Unlike the JMdict
homophone assets (phonetically IDENTICAL words), this captures Whisper's actual
acoustic near-confusions — voicing/dakuten, long/short vowel, geminate, mora boundary,
rendaku — the errors a dictionary can never predict.

For each labeled clip: Whisper(audio) vs gold; align tokens; every 'replace' span is a
real confusion (gold -> heard). Aggregate with counts. -> data/jp_asr_confusions.json
"""
import sys, os, glob, io, json, difflib, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import soundfile as sf
from faster_whisper import WhisperModel
from transcript_truth.verdict import _toks

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = WhisperModel("medium", device="cpu", compute_type="int8")

def surfaces(text):
    return [mo.surface() for mo in _toks(text)]

def whisper(wav):
    segs, _ = m.transcribe(wav, language="ja", task="transcribe")
    return "".join(s.text for s in segs).strip()

OUT = os.path.join(DIR, "data", "jp_asr_confusions.json")

def save(pairs, n):
    table = collections.defaultdict(list)
    for (g, h), c in pairs.items():
        table[g].append([h, c])
    for g in table:
        table[g].sort(key=lambda x: -x[1])
    json.dump({"_meta": {"clips": n, "pairs": len(pairs)}, "confusions": table},
              open(OUT, "w"), ensure_ascii=False, indent=0)

pairs = collections.Counter()
n = 0
for d in ("sounds", "sounds2"):
    for txt_f in sorted(glob.glob(os.path.join(DIR, "data", d, "*.txt"))):
        wav_f = txt_f[:-4] + ".wav"
        if not os.path.exists(wav_f):
            continue
        gold = open(txt_f, encoding="utf-8").read().strip()
        gt, ht = surfaces(gold), surfaces(whisper(wav_f))
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=gt, b=ht, autojunk=False).get_opcodes():
            if op == "replace":
                g, h = "".join(gt[i1:i2]), "".join(ht[j1:j2])
                g2, h2 = g.strip("、。・「」（）　 "), h.strip("、。・「」（）　 ")
                if g2 and h2 and g2 != h2:
                    pairs[(g2, h2)] += 1
        n += 1
        if n % 20 == 0:
            save(pairs, n)   # incremental save so a timeout never loses progress
            print(f"  {n} clips, {len(pairs)} distinct confusions (saved)", flush=True)

save(pairs, n)
print(f"\nDONE: {n} clips -> {len(pairs)} distinct ASR confusions -> {OUT}")
