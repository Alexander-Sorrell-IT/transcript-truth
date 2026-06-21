"""The Japanese-fluent WORKER (Qwen via NVIDIA). It does the Japanese; it never gets
the final word -- the deterministic auditor checks everything it produces.

No key in code: read from the gitignored .env next to the repo.
"""
import os, json, urllib.request

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
_MODEL = os.environ.get("QWEN_MODEL", "qwen/qwen3-next-80b-a3b-instruct")


def _key():
    k = os.environ.get("NVIDIA_API_KEY")
    if k:
        return k
    for line in open(os.path.join(_DIR, ".env"), encoding="utf-8"):
        if line.startswith("NVIDIA_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("NVIDIA_API_KEY not found in env or .env")


def qwen(messages, model=_MODEL, max_tokens=1024, temperature=0):
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    req = urllib.request.Request(_ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        msg = json.load(r)["choices"][0]["message"]
        # reasoning models may leave 'content' empty and put text in 'reasoning_content'
        return (msg.get("content") or msg.get("reasoning_content") or "").strip()


def correct_transcript(text):
    """Worker pass: clean a raw Japanese ASR transcript per GoTranscript rules. Carries
    the WORKER-side rules (the ones the auditor can't scan for): keep swear words, dash
    conventions, no exclamation. The auditor independently checks its output afterward."""
    prompt = (
        "あなたはGoTranscriptの日本語書き起こし校正者です。次の生の書き起こしを規則に従って校正してください。\n"
        "【規則】\n"
        "1. 同音異義語の誤りを文脈に合う正しい漢字に直す（例：動機→動悸、以外→意外）。\n"
        "2. 形式名詞・補助動詞・準体助詞は仮名に（下さい→ください、事→こと、と言う→という）。\n"
        "3. 悪態・罵倒の言葉も絶対に削除しない（例：馬鹿）。聞こえた通り残す。\n"
        "4. ダッシュ：言い直し／途中で途切れて続かない＝ダブルダッシュ「--」。中断したが話者が続けた＝シングルダッシュ「-」。\n"
        "5. ビックリマーク（！）は使わない。句点「。」にする。\n"
        "6. スラングは標準形に直す（すげぇー面白い→すごく面白い）。OK→オーケー。\n"
        "7. 説明・注釈は一切出力せず、校正後の本文だけを出力する。\n\n"
        f"生の書き起こし：\n{text}"
    )
    return qwen([{"role": "user", "content": prompt}])


def find_homophone_errors(text):
    """Coherence witness: Qwen scans for homophone mistakes BY MEANING (catches the
    thin-context cases collocation misses, e.g. 菓子90度 -> 華氏90度). Returns (wrong,
    right) pairs. The caller MUST verify each deterministically (same reading + real
    word) so Qwen can't hallucinate a correction."""
    prompt = (
        "次の日本語の文を読み、文脈に合わない同音異義語の取り違えだけを指摘してください。\n"
        "各指摘は必ず「誤→正」の形式で1行ずつ。同じ読みの別の漢字に限る。\n"
        "取り違えが無ければ「なし」とだけ書く。説明は不要。\n\n"
        f"文：{text}"
    )
    out = qwen([{"role": "user", "content": prompt}], max_tokens=200)
    pairs = []
    for line in out.splitlines():
        line = line.strip().lstrip("-・*0123456789. 　")
        if "→" in line:
            a, b = line.split("→", 1)
            a, b = a.strip(" 」「"), b.strip(" 」「（）()")
            if a and b and a != b:
                pairs.append((a, b))
    return pairs


def file_timestamp(total_minutes, n_parts, part_index, pos_seconds, embedded_hms=None):
    """Deterministic timestamp math (rules 5/8) — NO model. Whole-file [HH:MM:SS].
    If the customer said 'use the embedded time', pass embedded_hms='H:MM:SS' and it
    is used directly; otherwise compute (part-1)*part_length + position."""
    if embedded_hms:
        parts = [int(x) for x in embedded_hms.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, s = parts
    else:
        part_len_sec = total_minutes * 60 / n_parts
        total = int((part_index - 1) * part_len_sec + pos_seconds)
        h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"[{h:02d}:{m:02d}:{s:02d}]"
