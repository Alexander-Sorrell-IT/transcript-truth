"""Test the genuinely-ambiguous case: same-reading word pairs where BOTH fit
context. For each, check whether the system SURFACES the ambiguity (flags it for
human review) or silently passes it.

Two surfacing channels tested:
  (1) collocation.suggest_corrections(claim)  -- single-transcript coherence check
  (2) verdict.verify(claim, evidence)         -- claim vs independent ASR read,
       run in the realistic mode where the ASR heard the OTHER homophone of the
       same sound (this is exactly when an AMBIGUOUS verdict is supposed to fire).

"Perfect" = it is never silently passed: even if it can't auto-decide, it is flagged.
"""
from transcript_truth.verdict import verify
from transcript_truth.collocation import suggest_corrections

# (formA, formB, sentence-with-A, sentence-with-B) where both A and B are
# plausible in their sentence to a human (genuine homophone ambiguity).
CASES = [
    ("偏在", "遍在", "資源が地域に偏在している。",   "神は世界に遍在している。"),
    ("異常", "異状", "検査で異常が見つかった。",     "機体に異状はなかった。"),
    ("回答", "解答", "質問に回答してください。",     "問題の解答を確認した。"),
    ("配布", "配付", "資料を配布した。",            "願書を配付した。"),
    ("保証", "保障", "品質を保証する。",            "安全を保障する。"),
    ("意志", "意思", "強い意志を持つ。",            "本人の意思を尊重する。"),
    ("追求", "追究", "利益を追求する。",            "真理を追究する。"),
    ("成長", "生長", "子供が成長する。",            "植物が生長する。"),
    ("特長", "特徴", "製品の特長を説明する。",       "犯人の特徴を述べる。"),
    ("対称", "対象", "左右対称の図形だ。",          "調査の対象を選ぶ。"),
    ("観賞", "鑑賞", "魚を観賞する。",              "絵画を鑑賞する。"),
    ("決済", "決裁", "代金を決済する。",            "書類を決裁する。"),
]


def has_verdict(flags, kind):
    return any(f.get("verdict") == kind for f in flags)


print(f"{'pair':<10} {'suggest':<9} {'verify(A|B->ASR)':<18} {'surfaced?'}")
print("-" * 60)

n = len(CASES)
surfaced_suggest = 0
surfaced_verify = 0
surfaced_either = 0
rows = []

for A, B, sA, sB in CASES:
    # Channel 1: single-transcript coherence on the A-sentence
    sug = suggest_corrections(sA)
    sug_hit = len(sug) > 0

    # Channel 2: claim says A, the independent ASR read of the SAME audio heard B.
    # Same sound, both real words -> this is the textbook AMBIGUOUS trigger.
    # Build an evidence sentence identical to claim but with B swapped in for A.
    claim = sA
    evidence = sA.replace(A, B)
    vflags = verify(claim, evidence)
    v_amb = has_verdict(vflags, "AMBIGUOUS")
    # also note if verify emitted any flag at all for this span
    v_any = len(vflags) > 0

    if sug_hit:
        surfaced_suggest += 1
    if v_amb:
        surfaced_verify += 1
    if sug_hit or v_amb:
        surfaced_either += 1

    rows.append((A, B, sug_hit, v_amb, v_any, vflags, sug))
    print(f"{A}/{B:<7} {str(sug_hit):<9} {('AMBIGUOUS' if v_amb else ('other:'+','.join(f['verdict'] for f in vflags) if v_any else 'silent')):<18} {str(sug_hit or v_amb)}")

print("-" * 60)
print(f"Total cases: {n}")
print(f"suggest_corrections surfaced:  {surfaced_suggest}/{n}")
print(f"verify AMBIGUOUS surfaced:     {surfaced_verify}/{n}")
print(f"surfaced by EITHER channel:    {surfaced_either}/{n}")
print(f"SILENTLY PASSED by both:       {n - surfaced_either}/{n}")

print("\n--- detail of verify() flags per case (claim=A, ASR=B) ---")
for A, B, sug_hit, v_amb, v_any, vflags, sug in rows:
    print(f"\n{A}/{B}: claim sentence had {A}, ASR read {B}")
    if not vflags:
        print("   verify: (no flags -- SILENT)")
    for f in vflags:
        print(f"   verify: {f['verdict']} | {f.get('claim')} vs {f.get('audio')}")
    if sug:
        for s in sug:
            print(f"   suggest: written={s['written']} -> suggest={s['suggest']} (fit {s['written_fit']} vs {s['suggest_fit']})")
