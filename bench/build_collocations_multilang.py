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
import os, sys, json, re, collections, time

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR)
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "15000"))
MAX_SECONDS = int(os.environ.get("MAX_SECONDS", "900"))
TOP_N = int(os.environ.get("TOP_N", "30"))
_WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def tokenizer_for(lang):
    if lang == "ko":
        from kiwipiepy import Kiwi
        k = Kiwi()
        content = {"NNG", "NNP", "VV", "VA"}
        return lambda text: [t.form for t in k.tokenize(text)
                             if t.tag in content and len(t.form) > 1]
    # content-word filter with no hand lists: drop function words by frequency —
    # zipf >= 5.7 is 'de/le/und/que' territory in every language wordfreq covers.
    from wordfreq import zipf_frequency
    return lambda text: [w for w in (x.lower() for x in _WORD.findall(text))
                         if zipf_frequency(w, lang) < 5.7]


def build(lang):
    from datasets import load_dataset
    out_path = os.path.join(DIR, "data", f"{lang}_collocations.json")
    print(f"[{lang}] streaming Wikipedia 20231101.{lang} ...", flush=True)
    ds = load_dataset("wikimedia/wikipedia", f"20231101.{lang}",
                      split="train", streaming=True)
    tok = tokenizer_for(lang)
    pair = collections.Counter()
    start, n = time.time(), 0
    for art in ds:
        if n >= MAX_ARTICLES or time.time() - start > MAX_SECONDS:
            break
        words = tok(art["text"][:6000])
        for a, b in zip(words, words[1:]):
            pair[(a, b)] += 1
        n += 1
        if n % 2000 == 0:
            print(f"[{lang}] {n} articles, {len(pair)} pairs, "
                  f"{int(time.time()-start)}s", flush=True)

    by_word = collections.defaultdict(collections.Counter)
    for (a, b), c in pair.items():
        if c < 2:            # drop hapax pairs — noise, and shrinks the file 10x
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
