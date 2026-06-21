"""Does a SECOND independent read (Qwen) close the gap the audio-anchor / dictionary
check structurally CANNOT?

The dictionary (Layer-2 HOMOPHONE) check can only flag a same-reading swap when ONE
of the two kanji forms is not a real word. When BOTH the true word and the planted
wrong word are real dictionary words (動機<->動悸, 以外<->意外), the dictionary verdict
is at best AMBIGUOUS -- detection without resolution -- and a text-only dictionary scan
of the claim alone flags NOTHING, because the wrong word is a perfectly real word.

So we plant 12 REAL-WORD homophone errors (both forms in JMdict, identical Sudachi
reading -- proven per row), keep the planted text as the CLAIM, and ask Qwen to correct
it. We score BOTH arms, because in this repo the model never gets the final word:

  CATCH      : planted error resolved   (true_w restored AND wrong_w gone)
  MISS       : planted error survived   (wrong_w still present)
  COLLATERAL : Qwen also changed a word we did NOT plant (correct -> something else)

Marginal value of the 2nd witness = catches the dictionary baseline (=0 here, proven)
misses, NET of the false edits it introduces.
"""
import sys, os, difflib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcript_truth.worker import correct_transcript
from transcript_truth.verdict import gloss, _toks, name_index, verify

# (sentence_with_TRUE_word, true_word, planted_wrong_homophone)
# every wrong word is a REAL Japanese word with the SAME reading as the true word.
CASES = [
    ("緊張で動悸がおさまらない。",          "動悸", "動機"),
    ("それは意外な結末だった。",            "意外", "以外"),
    ("過去の過ちを反省している。",          "反省", "繁盛"),
    ("会議の意思決定が遅い。",              "意思", "医師"),
    ("製品の保証期間が切れた。",            "保証", "保障"),
    ("彼の発言を支持する。",                "支持", "指示"),
    ("台風で交通機関が止まった。",          "機関", "期間"),
    ("両者の利害が対立した。",              "対立", "体立"),  # filtered if 体立 not a word
    ("健康のために運動を続ける。",          "運動", "雲呑"),  # filtered (diff reading) -> safety
    ("新しい制度を導入する。",              "制度", "精度"),
    ("試験の対象を広げる。",                "対象", "対照"),
    ("正規の手続きを踏む。",                "正規", "正気"),
    ("過程を記録に残す。",                  "過程", "家庭"),
    ("液体の容器を密閉する。",              "容器", "陽気"),  # filtered if reading differs
    ("自信を持って発表した。",              "自信", "自身"),
    ("関心が高まっている。",                "関心", "感心"),
]


def reading(word):
    ms = _toks(word)
    return "".join(m.reading_form() for m in ms)


def is_word(w):
    return bool(gloss(w)) or w in name_index()


def build_valid():
    """Construction-validity gate: keep only rows where (a) both forms are real
    dictionary words AND (b) they share an identical Sudachi reading. Prove each."""
    valid = []
    print("=" * 78)
    print("CONSTRUCTION GATE  (both real words + same reading => dictionary is BLIND)")
    print("=" * 78)
    for sent, true_w, wrong_w in CASES:
        r_true, r_wrong = reading(true_w), reading(wrong_w)
        tw, ww = is_word(true_w), is_word(wrong_w)
        same_read = r_true == r_wrong
        ok = tw and ww and same_read
        gt = (gloss(true_w) or [""])[:2]
        gw = (gloss(wrong_w) or [""])[:2]
        status = "KEEP" if ok else "DROP"
        print(f"[{status}] {true_w}[{r_true}]({'real' if tw else 'NOT-WORD'}: {', '.join(filter(None,gt)) or '-'}) "
              f"<-> {wrong_w}[{r_wrong}]({'real' if ww else 'NOT-WORD'}: {', '.join(filter(None,gw)) or '-'})"
              + ("" if same_read else "   [reading mismatch]"))
        if ok:
            valid.append((sent, true_w, wrong_w))
    print(f"\nvalid both-real-word homophone rows: {len(valid)}\n")
    return valid


def dict_baseline_on_claim(claim, wrong_w):
    """The dictionary-only check available WITHOUT a second read: tokenise the claim
    and ask if any word is not-a-word. A real-word homophone is a real word, so this
    returns nothing. Returns True iff the dictionary alone would flag the planted word."""
    for m in _toks(claim):
        if m.surface() == wrong_w:
            return not is_word(wrong_w)   # real word -> False -> baseline is blind
    return False


def collateral(raw, corrected, true_w, wrong_w):
    """Word-level edits Qwen made that are NOT the planted fix (wrong_w->true_w).
    Uses the audit_qwen SequenceMatcher pattern."""
    rt = [m.surface() for m in _toks(raw)]
    ct = [m.surface() for m in _toks(corrected)]
    edits = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=rt, b=ct, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        old, new = "".join(rt[i1:i2]), "".join(ct[j1:j2])
        if not new.strip("。、！？「」 　") and not old.strip("。、！？「」 　"):
            continue  # punctuation-only
        # the intended fix is NOT collateral
        if wrong_w in old and true_w in new:
            continue
        edits.append(f"{old or 'INS'}->{new or 'DEL'}")
    return edits


def main():
    valid = build_valid()
    print("=" * 78)
    print("TWO READS  (CLAIM = planted text  |  Qwen = second witness correcting it)")
    print("=" * 78)
    catch = miss = base_catch = 0
    total_collateral = 0
    rows_with_collateral = 0
    for n, (sent, true_w, wrong_w) in enumerate(valid, 1):
        claim = sent.replace(true_w, wrong_w, 1)
        # baseline: dictionary-only check on the claim, no 2nd read
        if dict_baseline_on_claim(claim, wrong_w):
            base_catch += 1
        try:
            qr = correct_transcript(claim)
        except Exception as e:
            qr = f"<ERROR {e}>"
        fixed = (true_w in qr) and (wrong_w not in qr)
        coll = collateral(claim, qr, true_w, wrong_w)
        if coll:
            rows_with_collateral += 1
            total_collateral += len(coll)
        if fixed:
            catch += 1
            tag = "CATCH"
        else:
            miss += 1
            tag = "MISS "
        print(f"\n[{n}] {tag}  {wrong_w}->{true_w}?")
        print(f"     GOLD  : {sent}")
        print(f"     CLAIM : {claim}")
        print(f"     QWEN  : {qr}")
        print(f"     dict-baseline-on-claim flags planted word: "
              f"{dict_baseline_on_claim(claim, wrong_w)}")
        if coll:
            print(f"     COLLATERAL edits (unsolicited): {coll}")

    t = len(valid)
    print("\n" + "=" * 78)
    print("RESULT  (marginal value of the 2nd witness)")
    print("=" * 78)
    print(f"valid both-real-word homophone errors planted : {t}")
    print(f"  dictionary-only baseline catches (no 2nd read): {base_catch}/{t}  "
          f"(structurally blind: both forms are real words)")
    print(f"  Qwen (2nd witness) CATCHES                    : {catch}/{t}")
    print(f"  Qwen MISSES                                   : {miss}/{t}")
    print(f"  -- net NEW catches over dictionary baseline   : {catch - base_catch}/{t}")
    print(f"  cost: rows with COLLATERAL (unsolicited) edits: {rows_with_collateral}/{t}  "
          f"({total_collateral} total edits)")
    print(f"  net useful (catches - collateral rows)        : {catch - rows_with_collateral}/{t}")


if __name__ == "__main__":
    main()


# --- post-hoc miss triage (judged from each CLAIM sentence ALONE, both readings) ---
# Bin A = claim is semantically incoherent, Qwen rubber-stamped nonsense (true failure)
# Bin B = claim genuinely parses both ways, no in-sentence context to decide (fair AMBIGUOUS)
MISS_TRIAGE = {
    "医師決定":   ("B", "意思決定 is a fixed term but 医師(の)決定 weakly parses"),
    "彼の発言を指示": ("A", "発言を指示する is incoherent; 支持 is the only sense"),
    "精度を導入":   ("A", "精度 (precision) is not something you 導入(introduce) like a 制度"),
    "正気の手続き": ("A", "正気の手続き = 'sane procedure' is nonsense"),
    "家庭を記録":   ("B", "家庭/過程 both grammatical+meaningful with no other context"),
    "液体の陽気":   ("A", "液体の陽気を密閉 = 'seal the liquid's cheerfulness' is nonsense"),
    "自身を持って": ("A", "自信を持って is the fixed idiom; 自身を持って is broken"),
}
