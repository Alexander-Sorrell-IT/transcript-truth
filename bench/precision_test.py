"""Precision test: does verdict.verify() FALSE-ALARM on correct/equivalent input?

Recall (does it catch errors) was the only thing measured before. This measures the
OTHER half: feed it pairs that are genuinely EQUIVALENT (same word, different spelling;
identical text) and count how often it wrongly flags them. A usable QA tool must be
quiet on correct input. Also re-checks that real errors still flag (recall sanity).

No audio, no gold-on-both-sides leakage -- just the verdict logic on labeled pairs.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.verdict import verify

# EQUIVALENT: same meaning, different surface -> verify() MUST return [] (no flag).
EQUIVALENT = [
    ("珈琲", "コーヒー"), ("煙草", "タバコ"), ("顎", "あご"), ("有難う", "ありがとう"),
    ("林檎", "りんご"), ("飛行機", "ひこうき"), ("玉子", "卵"), ("林檎", "リンゴ"),
    ("東京", "東京"), ("日本語", "日本語"),                       # identical
    ("バルセロナ", "バルセロナ"), ("九龍", "九龍"),               # proper nouns, identical
]

# DIFFERENT: real mishearing or genuine homophone -> verify() MUST flag (recall sanity).
DIFFERENT = [
    ("群島", "軍島"),      # non-word mishearing
    ("記者", "汽車"),      # genuine same-reading homophone
    ("私立", "市立"),
    ("科学", "化学"),
    ("磁気反転", "時期判定"),  # different reading (SOUND layer)
]

fp = 0
print("=== EQUIVALENT pairs (must NOT flag) ===")
for c, e in EQUIVALENT:
    fl = verify(c, e)
    ok = (fl == [])
    if not ok:
        fp += 1
    print(f"  {'ok ' if ok else 'FALSE POSITIVE'}  {c} / {e}" + ("" if ok else f"  -> {fl[0]['verdict']}"))

missed = 0
print("\n=== DIFFERENT pairs (must flag) ===")
for c, e in DIFFERENT:
    fl = verify(c, e)
    ok = bool(fl)
    if not ok:
        missed += 1
    print(f"  {'ok ' if ok else 'MISSED'}  {c} / {e}" + (f"  -> {fl[0]['verdict']}" if fl else ""))

print("\n" + "=" * 56)
print(f"PRECISION: {len(EQUIVALENT)-fp}/{len(EQUIVALENT)} equivalent pairs correctly NOT flagged "
      f"({fp} false positives)")
print(f"RECALL   : {len(DIFFERENT)-missed}/{len(DIFFERENT)} real errors flagged ({missed} missed)")
