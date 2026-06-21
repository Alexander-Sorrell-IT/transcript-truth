"""Gate 1 — validate the 340-entry homophone KB against authoritative JMdict.

Builds a reverse-reading index from JMdict (reading -> set of kanji that carry it)
and for each KB entry checks:
  (a) FALSE member  — a listed kanji JMdict does NOT record with that reading
                      (likely a fabrication / mis-grouping)
  (b) MISSING member — a COMMON same-reading kanji the entry omits
                      (the こうせい/構成 gap class the synth predicted)
Honest: 'false' = JMdict-unconfirmed (could be a JMdict gap, review it). 'missing'
= candidate additions (not all are real confusables — that's the native step).
"""
import os, json, re, collections
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KANJI = re.compile(r"^[一-鿿]{2,4}$")


def build_index(path):
    data = json.load(open(path, encoding="utf-8"))
    idx = collections.defaultdict(set)
    for w in data["words"]:
        kanji = [k["text"] for k in w.get("kanji", [])]
        if not kanji:
            continue
        for kn in w.get("kana", []):
            for kj in kanji:
                idx[kn["text"]].add(kj)
    return idx


full = build_index(os.path.join(REPO, "data", "jmdict-eng-3.6.2.json"))
common = build_index(os.path.join(REPO, "data", "jmdict-eng-common-3.6.2.json"))

confirmed = json.load(open(os.path.join(REPO, "data", "jp_confirmed.json"), encoding="utf-8"))
results = []
n_homo = n_clean = n_false = n_missing = 0
for e in confirmed:
    reading = (e.get("reading") or "").strip()
    members = [(o.get("kanji") or "").strip() for o in (e.get("options") or [])]
    members = [m for m in members if KANJI.match(m)]
    if not reading or len(members) < 2:
        continue
    n_homo += 1
    fset = full.get(reading, set())
    false_m = [m for m in members if m not in fset]
    cset = {k for k in common.get(reading, set()) if KANJI.match(k)}
    missing = sorted(cset - set(members))
    n_false += bool(false_m)
    n_missing += bool(missing)
    n_clean += not (false_m or missing)
    results.append({"key": e.get("key"), "reading": reading, "members": members,
                    "false": false_m, "missing": missing})

json.dump(results, open(os.path.join(REPO, "data", "jp_jmdict_validation.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"JMdict index: {len(full)} readings (full), {len(common)} (common)")
print(f"homophone entries validated: {n_homo}")
print(f"  fully clean (no false, no common gap) : {n_clean}  ({100*n_clean//max(1,n_homo)}%)")
print(f"  with JMdict-unconfirmed members       : {n_false}")
print(f"  with missing common members (gaps)    : {n_missing}")
print("\n--- JMdict-unconfirmed members (review these) ---")
shown = 0
for r in results:
    if r["false"] and shown < 8:
        print(f"  {r['key']} ({r['reading']}): {r['false']}"); shown += 1
print("\n--- missing common same-reading kanji (gaps, e.g. こうせい) ---")
shown = 0
for r in results:
    if r["missing"] and shown < 8:
        print(f"  {r['key']} ({r['reading']}): +{r['missing'][:6]}"); shown += 1
