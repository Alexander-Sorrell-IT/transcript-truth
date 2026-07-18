#!/usr/bin/env python3
"""Recover English references for the FLEURS translation battery (ROADMAP Phase 8, task 1).

The real-audio battery (`make_real_battery.py`) saved only each clip's SOURCE-language gold text,
never the English parallel — so translation quality was never scorable. FLEURS is parallel via the
FLoRes sentence `id` (shared across every language config), so we recover the English reference:

  1. For each source language in the battery, stream its FLEURS config and build {normalized gold
     text -> FLoRes id}, matching each stored clip's gold text back to its id.
  2. Stream FLEURS en_us once and build {id -> English text}.
  3. Join: clip -> id -> English reference.

Writes bench/fleurs_en_refs.json = {clip_stem: {"id": int, "en": str, "lang": str}}. Incremental:
already-recovered stems are kept. Honest: a clip whose gold text can't be matched is reported and
skipped, never given a fabricated reference.

    python3 bench/fleurs_en_refs.py [lang ...]
"""
import os, sys, json, re, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for line in open(os.path.join(ROOT, ".env")):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1); os.environ[k.strip()] = v.strip()

FLEURS = {  # our code -> FLEURS config (mirror make_real_battery.py)
    "en": "en_us", "ja": "ja_jp", "es": "es_419", "fr": "fr_fr", "de": "de_de",
    "pt": "pt_br", "ru": "ru_ru", "uk": "uk_ua", "ko": "ko_kr", "tr": "tr_tr",
    "vi": "vi_vn", "ar": "ar_eg", "hi": "hi_in", "ur": "ur_pk",
}
BENCH = os.path.join(ROOT, "bench")
REAL = os.path.join(BENCH, "battery_real")
OUT = os.path.join(BENCH, "fleurs_en_refs.json")
IDS = os.path.join(BENCH, "fleurs_ids.json")   # {stem: [id, lang]} — persisted per-lang, resumable


def norm(s: str) -> str:
    """Whitespace/punctuation-free NFC fold for robust cross-stream text matching."""
    s = unicodedata.normalize("NFC", s or "")
    return re.sub(r"[\s\W_]+", "", s, flags=re.UNICODE).lower()


def clips_for(lang: str) -> dict:
    """{normalized gold text -> stem} for every stored battery clip in this language."""
    out = {}
    for fn in sorted(os.listdir(REAL)):
        if not fn.endswith(".json"):
            continue
        meta = json.load(open(os.path.join(REAL, fn), encoding="utf-8"))
        if meta.get("lang") != lang:
            continue
        out[norm(meta["text"])] = fn[:-5]  # strip .json
    return out


def main():
    from datasets import load_dataset
    langs = [a for a in sys.argv[1:]] or ["tr", "ar", "hi", "ur", "vi", "ja"]
    refs = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    # resumable id cache: {stem: [id, lang]} — persisted after EACH language so a timeout/kill
    # never loses matched ids (step 1 is the slow part; en_us resolution is a separate step).
    stem_id = {k: tuple(v) for k, v in
               (json.load(open(IDS, encoding="utf-8")) if os.path.exists(IDS) else {}).items()}

    # Step 1: recover each clip's FLoRes id from its source config (skip already-cached).
    for lang in langs:
        want = {k: v for k, v in clips_for(lang).items()
                if v not in refs and v not in stem_id}
        if not want:
            print(f"[{lang}] all ids already cached/recovered", flush=True)
            continue
        print(f"[{lang}] streaming {FLEURS[lang]} to recover {len(want)} ids …", flush=True)
        ds = load_dataset("google/fleurs", FLEURS[lang], split="test", streaming=True)
        for ex in ds:
            key = norm(ex["transcription"])
            if key in want:
                stem = want.pop(key)
                stem_id[stem] = (ex["id"], lang)
                print(f"  {stem} -> id {ex['id']}", flush=True)
            if not want:
                break
        for k, stem in want.items():
            print(f"  !! {stem}: gold text not matched in FLEURS stream — skipped", flush=True)
        json.dump({k: list(v) for k, v in stem_id.items()},
                  open(IDS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # persist per-lang

    # Step 2: resolve every cached id -> English text (one en_us stream). Resumable: only the ids
    # not yet in refs are needed; write refs as soon as en_us is exhausted or all are found.
    needed = {fid for stem, (fid, lang) in stem_id.items() if stem not in refs}
    if not needed:
        print(f"nothing new to resolve; {len(refs)} refs already written")
        return
    print(f"[en] streaming en_us for {len(needed)} ids …", flush=True)
    id_en = {}
    ds = load_dataset("google/fleurs", "en_us", split="test", streaming=True)
    for ex in ds:
        if ex["id"] in needed:
            id_en[ex["id"]] = ex["raw_transcription"] or ex["transcription"]
            if len(id_en) == len(needed):
                break
    for stem, (fid, lang) in stem_id.items():
        if stem in refs:
            continue
        if fid in id_en:
            refs[stem] = {"id": fid, "en": id_en[fid], "lang": lang}
        else:
            print(f"  !! {stem}: id {fid} not found in en_us stream — skipped", flush=True)
    json.dump(refs, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {len(refs)} refs -> {OUT}")


if __name__ == "__main__":
    main()
