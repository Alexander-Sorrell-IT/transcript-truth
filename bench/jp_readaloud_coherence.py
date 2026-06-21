"""Test the USER's pipeline on the 3 homophones the sound-check missed.

His idea: read the on-screen text OUT LOUD, translate the speech, and if the
meaning "makes no sense here" you caught the error -- no Japanese reading needed,
the judgment happens in English.

For each homophone the acoustic layer could NOT separate (identical reading),
take the WRONG sentence and the RIGHT sentence, speak each with macOS `say`,
translate the speech with Whisper, and print both English meanings side by side.
If the wrong one comes out incoherent / different -> his layer catches it.
"""
import os, subprocess, sys
from faster_whisper import WhisperModel

# (label, wrong, right) -- the 3 misses from jp_phonetic_validate, in full sentence context
CASES = [
    ("guntou",
     "軍島や湖では必ずしもヨットは必要ありません",
     "群島や湖では必ずしもヨットは必要ありません"),
    ("boueki-shou",
     "貿易拠点を設立したスペイン人貿易省によって名付けられました",
     "貿易拠点を設立したスペイン人貿易商によって名付けられました"),
]

m = WhisperModel("medium", device="cpu", compute_type="int8")

def say_to_wav(text, path):
    subprocess.run(["say", "-v", "Kyoko", text, "-o", path], check=True)

def translate(path):
    segs, _ = m.transcribe(path, language="ja", task="translate")
    return "".join(s.text for s in segs).strip()

def hear_ja(path):
    segs, _ = m.transcribe(path, language="ja", task="transcribe")
    return "".join(s.text for s in segs).strip()

for label, wrong, right in CASES:
    say_to_wav(wrong, "/tmp/_w.aiff")
    say_to_wav(right, "/tmp/_r.aiff")
    print("\n" + "=" * 70)
    print(f"CASE: {label}")
    print(f"  WRONG text : {wrong}")
    print(f"    read-aloud heard back : {hear_ja('/tmp/_w.aiff')}")
    print(f"    read-aloud TRANSLATED : {translate('/tmp/_w.aiff')}")
    print(f"  RIGHT text : {right}")
    print(f"    read-aloud heard back : {hear_ja('/tmp/_r.aiff')}")
    print(f"    read-aloud TRANSLATED : {translate('/tmp/_r.aiff')}")
print("\n(If WRONG translates to something incoherent vs RIGHT, the coherence layer catches the homophone.)")
