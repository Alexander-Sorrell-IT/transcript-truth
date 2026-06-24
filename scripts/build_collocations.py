"""Generic collocation-index builder from a Leipzig Corpora Collection package.

Leipzig ships precomputed co-occurrence with significance scores; we turn it into the
same shape JP uses (word -> [top companion words]) so the decision layer is identical
across languages. Reusable for ru/uk/es/en/ja — just point it at the corpus dir.

  python scripts/build_collocations.py <corpus_dir> <prefix> <out.json> <script>
  script: 'cyrillic' | 'latin'   (which alphabet to keep)
"""
import sys, os, json, collections, re

SCRIPTS = {
    "cyrillic": re.compile(r"^[а-яёіїєґ’'-]{2,}$"),
    "latin":    re.compile(r"^[a-záéíóúüñàâäôîïçœ’'-]{2,}$"),
}


def build(corpus_dir, prefix, out_path, script, topn=25, min_sig=6.0):
    rx = SCRIPTS[script]
    ok = lambda w: bool(rx.match(w))
    id2word = {}
    for line in open(os.path.join(corpus_dir, f"{prefix}-words.txt"), encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 2:
            id2word[p[0]] = p[1]
    comp = collections.defaultdict(list)
    for line in open(os.path.join(corpus_dir, f"{prefix}-co_s.txt"), encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 4:
            continue
        try:
            sig = float(p[3])
        except ValueError:
            continue
        if sig < min_sig:
            continue
        w1, w2 = id2word.get(p[0], "").lower(), id2word.get(p[1], "").lower()
        if not (ok(w1) and ok(w2)) or w1 == w2:
            continue
        comp[w1].append((w2, sig)); comp[w2].append((w1, sig))
    out = {}
    for w, lst in comp.items():
        lst.sort(key=lambda t: -t[1])
        seen, top = set(), []
        for x, _ in lst:
            if x not in seen:
                seen.add(x); top.append(x)
            if len(top) >= topn:
                break
        out[w] = top
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    return len(out)


if __name__ == "__main__":
    n = build(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print(f"wrote {sys.argv[3]} — {n} headwords")
