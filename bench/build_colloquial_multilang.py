#!/usr/bin/env python3
"""Build <lang>_colloquial.json for every non-JA language — the idiom/colloquial data cell JA gets
from JMdict (11k entries), sourced from kaikki.org (machine-readable Wiktionary extracts, same
authority class as JMdict: real glosses + idiomatic/colloquial/slang tags).

Two passes per language:
  1. pos-phrase + pos-proverb subsets (small files) — multiword idioms/proverbs, kept wholesale.
  2. the FULL dictionary, STREAMED (never saved to disk) — single-word entries kept only when a
     sense is tagged slang/colloquial/idiomatic/informal/figurative/vulgar.

Output shape mirrors data/jp_colloquial.json: [{form, reading, tags, gloss}].
Run: python3 bench/build_colloquial_multilang.py [lang ...]   (default: all 13)
"""
import os, sys, json, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAIKKI = {  # our lang code -> kaikki dictionary name
    "en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
    "ru": "Russian", "uk": "Ukrainian", "tr": "Turkish", "ko": "Korean", "vi": "Vietnamese",
    "ar": "Arabic", "hi": "Hindi", "ur": "Urdu",
}
KEEP_TAGS = {"slang", "colloquial", "idiomatic", "informal", "figuratively", "figurative",
             "vulgar", "humorous", "internet-slang", "dialectal", "verlan", "childish",
             "euphemistic", "ethnic-slur", "derogatory", "familiar"}


def _entry(obj, extra_tag=None):
    form = obj.get("word", "").strip()
    if not form:
        return None
    senses = obj.get("senses") or []
    glosses, tags = [], set()
    for s in senses:
        tags.update(t for t in (s.get("tags") or []) if isinstance(t, str))
        glosses += (s.get("glosses") or [])[:1]
    if extra_tag:
        tags.add(extra_tag)
    reading = ""
    for snd in obj.get("sounds") or []:
        if snd.get("ipa"):
            reading = snd["ipa"]; break
    return {"form": form, "reading": reading,
            "tags": sorted(tags & (KEEP_TAGS | {"phrase", "proverb"})) or sorted(tags)[:3],
            "gloss": "; ".join(dict.fromkeys(glosses))[:200]}


def _stream(url):
    req = urllib.request.Request(url, headers={"User-Agent": "transcript-truth-builder"})
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in r:
            try:
                yield json.loads(raw)
            except Exception:
                continue


def build(lang):
    name = KAIKKI[lang]
    out, seen = [], set()

    # pass 1 — phrase + proverb subsets (idioms wholesale)
    for pos in ("phrase", "proverb", "prep_phrase"):
        url = (f"https://kaikki.org/dictionary/{name}/pos-{pos}/"
               f"kaikki.org-dictionary-{name}-by-pos-{pos}.jsonl")
        try:
            n0 = len(out)
            for obj in _stream(url):
                e = _entry(obj, extra_tag=pos)
                if e and e["form"] not in seen:
                    seen.add(e["form"]); out.append(e)
            print(f"  [{lang}] pos-{pos}: +{len(out)-n0}", flush=True)
        except Exception as ex:
            print(f"  [{lang}] pos-{pos}: unavailable ({ex})", flush=True)

    # pass 2 — stream the full dictionary, keep tagged single words only
    url = f"https://kaikki.org/dictionary/{name}/kaikki.org-dictionary-{name}.jsonl"
    try:
        n0 = len(out)
        for obj in _stream(url):
            senses = obj.get("senses") or []
            if not any(KEEP_TAGS & set(s.get("tags") or []) for s in senses):
                continue
            e = _entry(obj)
            if e and e["form"] not in seen:
                seen.add(e["form"]); out.append(e)
        print(f"  [{lang}] tagged single words: +{len(out)-n0}", flush=True)
    except Exception as ex:
        print(f"  [{lang}] full-dict stream failed ({ex})", flush=True)

    path = os.path.join(ROOT, "data", f"{lang}_colloquial.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print(f"[{lang}] DONE: {len(out)} entries -> {path} "
          f"({os.path.getsize(path)//1024}KB)", flush=True)


if __name__ == "__main__":
    langs = sys.argv[1:] or list(KAIKKI)
    for lang in langs:
        build(lang)
