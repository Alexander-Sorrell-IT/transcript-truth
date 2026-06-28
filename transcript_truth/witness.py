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


def elevenlabs_diarize(audio_path, language=None):
    """ElevenLabs Scribe WITH diarization — a second *structured* witness alongside
    deepgram_structured. Returns [{start, end, speaker, text}] so speaker turns can be
    voted across independent diarizers instead of trusting one. speaker ids are the raw
    Scribe labels (speaker_0, speaker_1, ...); the consensus layer maps them to roles."""
    import mimetypes
    boundary = "----ttboundary7f3a"
    fields = {"model_id": "scribe_v1", "diarize": "true", "timestamps_granularity": "word"}
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
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    turns, cur = [], None
    for w in d.get("words", []):
        if w.get("type") not in ("word", None):
            if cur is not None:
                cur["text"] += w.get("text", "")
            continue
        spk = w.get("speaker_id", "?")
        if cur is None or cur["speaker"] != spk:
            if cur:
                turns.append(cur)
            cur = {"start": w.get("start", 0.0), "end": w.get("end", 0.0),
                   "speaker": spk, "text": w.get("text", "")}
        else:
            cur["text"] += w.get("text", "")
            cur["end"] = w.get("end", cur["end"])
    if cur:
        turns.append(cur)
    return [{**t, "text": t["text"].strip()} for t in turns if t["text"].strip()]


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


def gemini_video_read(video_path, language=None):
    """Gemini video witness — the VISUAL read for a CCSL (continuity logger). Watches the
    whole reel and returns a raw JSON-array string (one object per shot); the ccsl_build
    half parses it. This supplies shot DESCRIPTION + on-screen OCR only — it carries NO
    authoritative timing (ffmpeg/PySceneDetect own every timecode) and is deliberately
    kept OFF the consensus roster: it emits caption/continuity output, not verbatim speech,
    so it would poison the token-majority vote.

    Four REST steps against the Gemini Files API (raw urllib), reusing the 503/429/500
    model-cascade pattern of `gemini_read`. Raises on missing key / HTTP error exactly
    like its siblings — the builder is responsible for the try/except graceful-degrade."""
    import time
    key = _key("GEMINI_API_KEY")
    data = open(video_path, "rb").read()

    # 1) start a resumable upload — read back the upload URL from the response header.
    start = urllib.request.Request(
        "https://generativelanguage.googleapis.com/upload/v1beta/files",
        data=json.dumps({"file": {"display_name": "reel"}}).encode(),
        headers={
            "x-goog-api-key": key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(data)),
            "X-Goog-Upload-Header-Content-Type": "video/mp4",
            "Content-Type": "application/json",
        })
    with urllib.request.urlopen(start, timeout=120) as r:
        upload_url = r.headers.get("x-goog-upload-url")

    # 2) upload the bytes and finalize — read back the file name/uri.
    up = urllib.request.Request(upload_url, data=data, headers={
        "x-goog-api-key": key,
        "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize",
        "Content-Type": "video/mp4"})
    with urllib.request.urlopen(up, timeout=600) as r:
        f = json.load(r)["file"]
    name, uri = f["name"], f["uri"]

    # 3) poll until the file is ACTIVE (Gemini transcodes large video server-side).
    for _ in range(60):
        poll = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/{name}",
            headers={"x-goog-api-key": key})
        with urllib.request.urlopen(poll, timeout=120) as r:
            st = json.load(r).get("state")
        if st == "ACTIVE":
            break
        time.sleep(5)

    prompt = (
        "You are a continuity logger. Watch the entire video. Output a JSON array, one "
        "object per distinct camera shot in chronological order, keys: 't' (MM:SS), 'shot' "
        "(WS/MS/CU/insert/title card), 'action' (one line), 'onscreen_text' (verbatim OCR "
        "or \"\"). Output only the JSON array.")
    body = json.dumps({
        "contents": [{"parts": [
            {"text": prompt},
            {"file_data": {"mime_type": "video/mp4", "file_uri": uri}}]}],
        "generationConfig": {"response_mime_type": "application/json"}}).encode()

    # 4) generateContent with the same overloaded -> next-model cascade as gemini_read.
    models = ["gemini-2.5-pro", "gemini-2.5-flash"]
    last = None
    for mdl in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent"
        req = urllib.request.Request(url, data=body, headers={
            "x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (503, 429, 500):   # overloaded/rate-limited -> try next model
                continue
            raise
    raise last
