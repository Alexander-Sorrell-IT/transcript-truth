"""Language-aware numeric VALUE extraction — the deterministic core of translation survival
checks (and reusable anywhere numbers must be compared across languages/formats).

`values(text, lang)` returns a Counter of numeric values found in `text`, where a value can be
written as digits ("40000", "40.000", "٤٠٠٠٠") or spelled in the language ("kırk bin",
"doce mil", "四万"). Cross-language comparison then reduces to comparing Counters — '17' in the
English translation matches 'on yedi' in the Turkish source because both extract as 17.

Spelled-number parsing is built by INVERTING num2words (already a dependency): for each language
we generate the spelled forms of 0-99, the hundreds, and the scale words (1000, 10^4 for CJK,
10^6, 10^9), fold them, and parse token runs with a standard unit+scale accumulator. Languages
num2words can't spell (hi, ur) parse digits only and report spelled_support=False so callers can
mark a numbers check UNVERIFIABLE instead of vacuously passing it.

Locale digit rules: comma-decimal languages (de/es/fr/pt/tr/ru/uk/vi) read "2,5" as 2.5 and
"12.000" as 12000; dot-decimal languages read "2.5" as 2.5 and "12,000" as 12000. Grouping is
only accepted for exactly-3-digit groups, so "5,10" (a list) never becomes 510.
"""
from __future__ import annotations
import functools
import re
import unicodedata
from collections import Counter

# languages where ',' is the decimal separator and '.' groups thousands
_COMMA_DECIMAL = {"de", "es", "fr", "pt", "tr", "ru", "uk", "vi"}

# per-language scale words worth inverting (CJK counts in 10^4s)
_SCALES = (100, 1000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000, 1_000_000_000)


def _fold(s: str) -> str:
    """Case/diacritic/separator fold for spelled-number matching (Turkish 'kırk' vs 'Kırk',
    hyphenated French 'dix-sept'). Keeps non-Latin scripts intact."""
    s = s.lower().replace("-", "").replace("­", "")
    s = unicodedata.normalize("NFC", s)
    return s


@functools.lru_cache(maxsize=32)
def _tables(lang: str):
    """(units: {folded-word: value}, scales: {folded-word: scale}, ok: bool) for a language.
    Built once by inverting num2words; ok=False when num2words lacks the language."""
    try:
        from num2words import num2words
        num2words(1, lang=lang)
    except Exception:
        return {}, {}, False
    from num2words import num2words
    units: dict[str, int] = {}
    for n in list(range(0, 100)) + [h * 100 for h in range(1, 10)]:
        try:
            w = _fold(num2words(n, lang=lang))
        except Exception:
            continue
        units[w] = n
        units[w.replace(" ", "")] = n            # 'kırk bin' speech vs 'kırkbin' joined
    one = ""
    try:
        one = _fold(num2words(1, lang=lang))
    except Exception:
        pass
    scales: dict[str, int] = {}
    for s in _SCALES:
        try:
            w = _fold(num2words(s, lang=lang))
        except Exception:
            continue
        scales[w.replace(" ", "")] = s
        if one and w.startswith(one):            # ja 一万 -> 万 ; strip the unit prefix
            bare = w[len(one):].strip().replace(" ", "")
            if bare:
                scales[bare] = s
    return units, scales, True


def spelled_support(lang: str) -> bool:
    """Can spelled-out numbers in this language be parsed? (hi/ur: no — digits only.)"""
    return _tables(lang)[2]


def _digit_values(text: str, lang: str) -> list[float]:
    """Digit-run values with locale-aware separators; native digits folded to ASCII first."""
    if any(ch.isdigit() and not ch.isascii() for ch in text):
        text = "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch
                       for ch in text)
    comma_dec = lang.split("-")[0] in _COMMA_DECIMAL
    group, dec = (".", ",") if comma_dec else (",", ".")
    out = []
    for m in re.finditer(r"\d[\d.,]*\d|\d", text):
        raw = m.group(0)
        # grouping separators are only real when every group is exactly 3 digits
        parts = raw.split(group)
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) and parts[0].isdigit():
            raw = "".join(parts)
        raw = raw.replace(dec, ".")
        raw = re.sub(r"[.,](?=.*[.,])", "", raw)          # any leftover separators: keep last
        try:
            v = float(raw)
        except ValueError:
            continue
        out.append(int(v) if v == int(v) else v)
    return out


_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힣]")

# words num2words writes INSIDE a number ('one hundred AND forty') — transparent mid-number
_CONNECTORS = {"and", "und", "y", "et", "e", "و", "i", "и"}
_CONN = "\x00conn"


def _spelled_values(text: str, lang: str) -> list[float]:
    """Spelled-number values via the inverted num2words tables + unit/scale accumulator.
    Three matching modes cover how languages write numbers out:
      - multi-token lookahead: Arabic 17 = 'سبعة عشر' (seven-ten across two tokens);
      - whole-token compounds: Turkish 'onyedi' splits by greedy prefix;
      - intra-token scan for CJK: '十七人が…' has no spaces — number-words are extracted from
        inside the run, non-number chars flush.
    Unknown words flush the current accumulation."""
    units, scales, ok = _tables(lang)
    if not ok:
        return []
    vocab = set(units) | set(scales)

    # number-word "bits" in reading order; None = flush marker (a non-number word/char)
    bits: list[str | None] = []
    toks = [_fold(t) for t in re.findall(r"[^\s,.;:!?()\[\]«»\"']+", text)]
    i = 0
    while i < len(toks):
        # 1) longest multi-token join (space-stripped keys hold 'سبعة عشر' as 'سبعةعشر')
        matched = False
        for k in range(min(4, len(toks) - i), 1, -1):
            joined = "".join(toks[i:i + k])
            if joined in vocab:
                bits.append(joined)
                i += k
                matched = True
                break
        if matched:
            continue
        tok = toks[i]
        i += 1
        if tok in vocab:
            bits.append(tok)
            continue
        if tok in _CONNECTORS:
            bits.append(_CONN)
            continue
        if _CJK.search(tok):
            # 2) intra-token scan: extract number-word substrings, flush on other chars
            j = 0
            while j < len(tok):
                for k in range(len(tok), j, -1):
                    if tok[j:k] in vocab:
                        bits.append(tok[j:k])
                        j = k
                        break
                else:
                    bits.append(None)
                    j += 1
            continue
        # 3) whole-token greedy prefix split (joined Latin compounds: 'onyedi', 'kırkbin')
        sub, j, good = [], 0, True
        while j < len(tok):
            for k in range(len(tok), j, -1):
                if tok[j:k] in vocab:
                    sub.append(tok[j:k])
                    j = k
                    break
            else:
                good = False
                break
        bits.extend(sub if good and sub else [None])

    out, cur, total, in_num = [], 0, 0, False
    for idx, b in enumerate(bits):
        if b == _CONN:
            # soft connector ('one hundred AND forty seven'): transparent inside a number
            # when a number-word follows; otherwise it flushes like any other word
            if in_num and idx + 1 < len(bits) and bits[idx + 1] not in (None, _CONN):
                continue
            b = None
        if b is None:
            if in_num:
                out.append(total + cur)
                cur = total = 0
                in_num = False
            continue
        if b in scales:
            s = scales[b]
            if s == 100:
                cur = max(cur, 1) * 100
            else:
                total += max(cur, 1) * s
                cur = 0
        else:
            u = units[b]
            # place-value validity: a unit may only fill a SMALLER place than what's already
            # accumulated ('forty seven' ok; 'nineteen ninety' is TWO numbers — decade-style
            # years must split as 19+95, never silently sum to 114)
            valid = (cur == 0
                     or (u < 10 and cur % 10 == 0 and cur % 100 != 0 or u < 10 and cur >= 100 and cur % 100 == 0)
                     or (10 <= u < 100 and cur >= 100 and cur % 100 == 0)
                     or (u >= 100 and cur % 1000 == 0 and cur > 0))
            if cur == 0:
                cur = u
            elif valid:
                cur += u
            else:
                out.append(total + cur)                    # flush: a NEW number starts here
                cur, total = u, 0
        in_num = True
    if in_num:
        out.append(total + cur)
    return [v for v in out if v != 0]                     # lone zeros are usually 'O'/fillers


def values(text: str, lang: str = "en") -> Counter:
    """All numeric values in `text` (digits + spelled), as a multiset. The cross-language
    comparable representation: values('on yedi kişi','tr') == values('17 people','en')."""
    lang = (lang or "en").split("-")[0]
    return Counter(_digit_values(text, lang)) + Counter(_spelled_values(text, lang))
