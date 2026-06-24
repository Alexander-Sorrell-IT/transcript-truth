"""Independent acoustic witnesses — strong ASRs of a different family than Whisper.
ElevenLabs Scribe (beats Whisper on Japanese FLEURS) is the primary second read.
Where Whisper and Scribe AGREE -> high confidence. Where they DISAGREE -> flag for a
human ear. Two strong, differently-built models don't make the identical mistake, so
their disagreement surfaces the correlated errors a single model can't self-detect.
Keys live in the gitignored .env.
"""
import os, json, urllib.request

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _key(name):
    v = os.environ.get(name)
    if v:
        return v
    for line in open(os.path.join(_DIR, ".env"), encoding="utf-8"):
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{name} not found")


def elevenlabs_read(audio_path, language=None):
    """ElevenLabs Scribe — the strong second read (different family than Whisper)."""
    import mimetypes
    boundary = "----ttboundary7f3a"
    fields = {"model_id": "scribe_v1"}
    if language:
        fields["language_code"] = language
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    fn = os.path.basename(audio_path)
    ctype = mimetypes.guess_type(audio_path)[0] or "audio/mpeg"
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fn}\"\r\n"
             f"Content-Type: {ctype}\r\n\r\n").encode()
    body += open(audio_path, "rb").read() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=body, headers={
        "xi-api-key": _key("ELEVENLABS_API_KEY"),
        "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r).get("text", "").strip()


def gemini_read(audio_path, language=None):
    """Gemini (multimodal LLM) — a 4th independent witness, different family again.
    Strong on accented/bilingual speech because it reasons over context, not just acoustics."""
    import base64, mimetypes
    audio = base64.b64encode(open(audio_path, "rb").read()).decode()
    ctype = mimetypes.guess_type(audio_path)[0] or "audio/mpeg"
    if language and language.lower() not in ("ja", "jpn", "japanese"):
        instr = ("Transcribe this audio verbatim, exactly as spoken, in its original language. "
                 "Do not translate. Output only the transcript text.")
    else:
        instr = ("Transcribe this audio verbatim, exactly as spoken. Keep Japanese in Japanese "
                 "and English in English (do not translate). Output only the transcript text.")
    body = json.dumps({"contents": [{"parts": [
        {"text": instr}, {"inline_data": {"mime_type": ctype, "data": audio}}]}]}).encode()
    key = _key("GEMINI_API_KEY")
    models = ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    last = None
    for mdl in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent"
        req = urllib.request.Request(url, data=body, headers={
            "x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (503, 429, 500):   # overloaded/rate-limited -> try next model
                continue
            raise
    raise last


def hf_read(audio_path, language=None, model="openai/whisper-large-v3"):
    """Whisper-large-v3 via Hugging Face Inference Providers (free tier; multilingual,
    auto-detects language). A 5th witness — adds the Whisper family to the consensus.
    The legacy api-inference.huggingface.co host is dead; this uses the router endpoint."""
    import mimetypes
    ctype = mimetypes.guess_type(audio_path)[0] or "audio/wav"
    req = urllib.request.Request(
        f"https://router.huggingface.co/hf-inference/models/{model}",
        data=open(audio_path, "rb").read(),
        headers={"Authorization": "Bearer " + _key("HF_API_KEY"), "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r).get("text", "").strip()


def deepgram_structured(audio_path, language="en"):
    """Deepgram with diarization + utterances + timestamps — the structured backbone for
    the transcription runner. Returns [{start, end, speaker, text}]. (Scribe/Gemini stay
    text-only; Deepgram is the timing/speaker reference — and our 0% WER witness.)"""
    url = (f"https://api.deepgram.com/v1/listen?model=nova-3&language={language}"
           "&smart_format=true&diarize=true&utterances=true&punctuate=true")
    req = urllib.request.Request(url, data=open(audio_path, "rb").read(), headers={
        "Authorization": "Token " + _key("DEEPGRAM_API_KEY"), "Content-Type": "audio/wav"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    utts = d.get("results", {}).get("utterances", [])
    return [{"start": u.get("start", 0.0), "end": u.get("end", 0.0),
             "speaker": u.get("speaker", 0), "text": u.get("transcript", "").strip()}
            for u in utts if u.get("transcript", "").strip()]


def deepgram_read(audio_path, language="ja"):
    """Deepgram Nova — backup witness (weaker on bilingual audio; use for clean speech)."""
    url = f"https://api.deepgram.com/v1/listen?model=nova-3&language={language}&smart_format=true"
    req = urllib.request.Request(url, data=open(audio_path, "rb").read(), headers={
        "Authorization": "Token " + _key("DEEPGRAM_API_KEY"), "Content-Type": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return d["results"]["channels"][0]["alternatives"][0]["transcript"].strip()
