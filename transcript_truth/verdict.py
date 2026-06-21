"""Two-layer transcription verdict -- RoboTruth applied to audio.

No model in the verdict path. Given a candidate transcript (the CLAIM) and the
audio (the EVIDENCE), an independent ASR read of the audio is compared to the
claim, and every divergence is judged by two deterministic layers:

  Layer 1 -- SOUND     : the two reads differ in READING (kana) -> mishearing.
                         Caught by string comparison. (the 44/47 case)
  Layer 2 -- HOMOPHONE : identical reading, different kanji -> look up each form
                         in JMdict.  one a real word + the other not -> flag the
                         non-word.  both real words -> AMBIGUOUS (surface both
                         glosses, never fake a verdict).

You need zero Japanese to read this verdict: every flag is kana strings and
English dictionary glosses.
"""
import json, glob, os, difflib, functools
from sudachipy import dictionary, tokenizer

_tok = dictionary.Dictionary().create()
_MODE = tokenizer.Tokenizer.SplitMode.C
_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@functools.lru_cache(maxsize=1)
def gloss_index():
    """kanji surface -> list of English glosses, from JMdict common."""
    # prefer the FULL JMdict (~217k words) over the 22k "common" slice for word-existence
    # coverage; fall back to common if the full file isn't present.
    _full = [p for p in glob.glob(os.path.join(_DIR, "data", "*jmdict*eng*")) if "common" not in p]
    f = sorted(_full)[0] if _full else sorted(glob.glob(os.path.join(_DIR, "data", "*jmdict*common*")))[0]
    idx = {}
    for w in json.load(open(f))["words"]:
        glosses = []
        for s in w["sense"]:
            glosses += [g["text"] for g in s.get("gloss", [])]
        for k in w.get("kanji", []):
            idx.setdefault(k["text"], [])
            idx[k["text"]] += glosses
        # also index kana headwords (コーヒー, ありがとう) — a correct kana spelling of a
        # word that has a kanji form is still a real word; not indexing it caused
        # false LIKELY_MISHEARD flags on common katakana/hiragana spellings.
        for r in w.get("kana", []):
            idx.setdefault(r["text"], [])
            idx[r["text"]] += glosses
    return idx


def _toks(s):
    return _tok.tokenize(s, _MODE)


def _is_kana(s):
    """True if s is written purely in hiragana/katakana (a kana spelling of a word)."""
    return bool(s) and all("ぁ" <= c <= "ゟ" or "ァ" <= c <= "ヿ" or c == "ー" for c in s)


def gloss(surface):
    return gloss_index().get(surface)


@functools.lru_cache(maxsize=1)
def name_index():
    """Set of proper-noun surfaces (JMnedict): place/person/org names. A token that
    is a known name is a real word, not a mishearing (バルセロナ, 九龍, ファティマ)."""
    f = os.path.join(_DIR, "data", "jp_name_surfaces.json")
    try:
        return set(json.load(open(f, encoding="utf-8")))
    except FileNotFoundError:
        return set()


_KANSUJI = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
            "七": 7, "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "万": 10000, "億": 10**8}


def _num(s):
    """Canonical integer value of a numeric span (arabic OR kansuji), else None — so
    100 and 百 reconcile instead of reading as a mishearing."""
    import unicodedata
    s = unicodedata.normalize("NFKC", s)
    if s.isdigit():
        return int(s)
    if s and all(c in _KANSUJI for c in s):
        total = cur = 0
        for c in s:
            v = _KANSUJI[c]
            if v >= 10:
                cur = (cur or 1) * v; total += cur; cur = 0
            else:
                cur = cur * 10 + v
        return total + cur
    return None


_BENIGN_POS = {"助詞", "助動詞", "感動詞", "補助記号", "空白"}


def _all_benign(morphs):
    """True if every morpheme is a particle / auxiliary / filler / punctuation — a span
    of these added or dropped by ASR is a benign omission/addition, not a mishearing."""
    for m in morphs:
        pos = m.part_of_speech()
        if pos[0] in _BENIGN_POS or "フィラー" in pos:
            continue
        if not m.surface().strip("、。・「」（）　 "):
            continue
        return False
    return True


def verify(claim: str, evidence_text: str):
    """claim = submitted transcript; evidence_text = independent ASR read of the
    audio. Returns a receipt: list of flags, each fully readable without Japanese."""
    cm, em = list(_toks(claim)), list(_toks(evidence_text))
    cs = [m.surface() for m in cm]; es = [m.surface() for m in em]
    cr = [m.reading_form() for m in cm]; er = [m.reading_form() for m in em]
    flags = []
    sm = difflib.SequenceMatcher(a=cs, b=es, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        c_surf, e_surf = "".join(cs[i1:i2]), "".join(es[j1:j2])
        c_read, e_read = "".join(cr[i1:i2]), "".join(er[j1:j2])
        # ignore punctuation-only spans (記号 reads as empty / the marks themselves)
        if not c_surf.strip("、。・「」（）　 ") and not e_surf.strip("、。・「」（）　 "):
            continue
        # benign omission/addition: a particle/filler dropped or added by ASR is expected
        # (私はパン vs 私パン; an inserted えーと), NOT a mishearing
        if op == "delete" and _all_benign(cm[i1:i2]):
            continue
        if op == "insert" and _all_benign(em[j1:j2]):
            continue
        # number normalization: 100 vs 百 read differently (イチレイレイ vs ヒャク) but are
        # the same number -> not a mishearing
        cn = _num(c_surf)
        if cn is not None and cn == _num(e_surf):
            continue
        if c_read != e_read:
            flags.append({
                "layer": "SOUND", "verdict": "MISHEARD",
                "claim": f"{c_surf}[{c_read}]", "audio": f"{e_surf}[{e_read}]",
                "why": "the written reading does not match what the audio says",
            })
        else:
            # identical reading, different surface -> dictionary + proper-noun list decide
            cg, eg = gloss(c_surf), gloss(e_surf)
            c_name, e_name = c_surf in name_index(), e_surf in name_index()
            c_known, e_known = bool(cg) or c_name, bool(eg) or e_name
            cd = ", ".join(cg[:3]) if cg else ("proper noun/name" if c_name else "(not a known word)")
            ed = ", ".join(eg[:3]) if eg else ("proper noun/name" if e_name else "(not a known word)")
            if c_known and not e_known:
                flags.append({"layer": "HOMOPHONE", "verdict": "LIKELY_MISHEARD",
                    "claim": f"{c_surf} = {cd}", "audio": f"{e_surf} = {ed}",
                    "why": "same sound; audio's form is not a known word/name, claim is"})
            elif e_known and not c_known:
                flags.append({"layer": "HOMOPHONE", "verdict": "CLAIM_NOT_A_WORD",
                    "claim": f"{c_surf} = {cd}", "audio": f"{e_surf} = {ed}",
                    "why": "same sound; claim's form is not a known word/name"})
            elif c_known and e_known:
                _overlap = bool(cg and eg and (set(cg) & set(eg)))
                _variant = _overlap and (_is_kana(c_surf) or _is_kana(e_surf)
                                         or set(cg) <= set(eg) or set(eg) <= set(cg))
                if _variant:
                    # same word, different SPELLING: kana-vs-kanji of one word (珈琲/コーヒー,
                    # あご/顎), or one gloss set contained in the other. Not an error; skip.
                    # Two DISTINCT kanji that merely share a gloss (回答/解答 = reply vs
                    # solution) are NOT variants -> they fall through and surface.
                    continue
                # pitch-accent witness: same kana, but if the two forms have DIFFERENT
                # Tokyo pitch accent the audio CAN decide -- tell the listener what to
                # hear. Same accent (華氏/菓子, 動悸/動機) -> genuinely context-only.
                from .pitch_accent import distinguish as _pa, hint as _pahint
                _d = _pa(c_surf, e_surf, c_read)
                if _d["distinguishable"]:
                    flags.append({"layer": "HOMOPHONE", "verdict": "PITCH_RESOLVABLE",
                        "claim": f"{c_surf} = {cd}", "audio": f"{e_surf} = {ed}",
                        "why": "same kana but DIFFERENT pitch accent -- listen to decide: "
                               + _pahint(c_surf, e_surf, c_read)})
                else:
                    flags.append({"layer": "HOMOPHONE", "verdict": "AMBIGUOUS",
                        "claim": f"{c_surf} = {cd}", "audio": f"{e_surf} = {ed}",
                        "why": "same sound AND same pitch accent -- audio alone cannot decide; "
                               "context/human picks" if _d["have_data"] else
                               "same sound, different meaning -- audio alone cannot decide; human picks"})
            else:
                # both forms unknown to dictionary AND name list, same reading, surfaces differ:
                # don't silently drop it -- surface it as unverifiable for a human.
                flags.append({"layer": "HOMOPHONE", "verdict": "UNVERIFIABLE",
                    "claim": f"{c_surf} = (not in dictionary)",
                    "audio": f"{e_surf} = (not in dictionary)",
                    "why": "same sound, neither form is a known word -- needs a human ear"})
    return flags
