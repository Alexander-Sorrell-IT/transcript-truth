"""Generic per-language collocation builder — the SAME data cell Japanese has
(jp_collocations.json), built identically for every language: stream Wikipedia,
tokenize, count adjacent content-word bigrams, save top co-occurrences per word
to data/<lang>_collocations.json (the shape decision.py / adjudicate consume).

One algorithm, no per-language hand-tuning. Tokenization is picked by script:
  - ko  -> Kiwi content morphemes (NNG/NNP/VV/VA)
  - ja  -> (already built via Sudachi; skipped here)
  - all others -> unicode word regex, len>1, lowercased

Run:  python3 bench/build_collocations_multilang.py fr de pt tr ko vi ar hi ur
Env:  MAX_ARTICLES (default 15000), MAX_SECONDS per lang (default 900), TOP_N (30)
"""
import os, sys, json, collections, time
import regex as re  # stdlib re splits Indic words at combining marks (matras)

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR)
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "15000"))
MAX_SECONDS = int(os.environ.get("MAX_SECONDS", "900"))
TOP_N = int(os.environ.get("TOP_N", "30"))
_WORD = re.compile(r"[\p{L}\p{M}]{2,}")


def tokenizer_for(lang):
    if lang == "ko":
        from kiwipiepy import Kiwi
        k = Kiwi()
        content = {"NNG", "NNP", "VV", "VA"}
        return lambda text: [t.form for t in k.tokenize(text)
                             if t.tag in content and len(t.form) > 1]
    return lambda text: [w.lower() for w in _WORD.findall(text)]


def build(lang):
    from datasets import load_dataset
    out_path = os.path.join(DIR, "data", f"{lang}_collocations.json")
    print(f"[{lang}] streaming Wikipedia 20231101.{lang} ...", flush=True)
    ds = load_dataset("wikimedia/wikipedia", f"20231101.{lang}",
                      split="train", streaming=True)
    tok = tokenizer_for(lang)
    pair, unigram = collections.Counter(), collections.Counter()
    start, n = time.time(), 0
    for art in ds:
        if n >= MAX_ARTICLES or time.time() - start > MAX_SECONDS:
            break
        words = tok(art["text"][:6000])
        unigram.update(words)
        for a, b in zip(words, words[1:]):
            pair[(a, b)] += 1
        n += 1
        if n % 2000 == 0:
            print(f"[{lang}] {n} articles, {len(pair)} pairs, "
                  f"{int(time.time()-start)}s", flush=True)

    # corpus-derived stopwords by frequency SHARE, not rank: true function words
    # each hog >=0.2% of all tokens in any language (fr 'de'~5%, hi 'के'~4%),
    # while even very common content words sit far below (fr 'guerre'~0.05%).
    # Rank-based top-N ate real content words; a fixed wordfreq-zipf cutoff was
    # miscalibrated for hi/ur. Share is self-calibrating everywhere.
    total = sum(unigram.values()) or 1
    stop = {w for w, c in unigram.most_common(400) if c / total >= 0.002}
    by_word = collections.defaultdict(collections.Counter)
    for (a, b), c in pair.items():
        if c < 2 or a in stop or b in stop:
            continue
        by_word[a][b] += c
        by_word[b][a] += c
    table = {w: [x for x, _ in cnt.most_common(TOP_N)]
             for w, cnt in by_word.items() if sum(cnt.values()) >= 3}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False)
    print(f"[{lang}] DONE: {n} articles -> {len(table)} words "
          f"({os.path.getsize(out_path)//1048576}MB)", flush=True)


if __name__ == "__main__":
    langs = sys.argv[1:] or ["fr", "de", "pt", "tr", "ko", "vi", "ar", "hi", "ur"]
    for lang in langs:
        try:
            build(lang)
        except Exception as e:
            print(f"[{lang}] FAILED: {e}", flush=True)
