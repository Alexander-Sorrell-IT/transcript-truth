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


def elevenlabs_read(audio_path, language=None):  # pragma: no cover
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


def elevenlabs_diarize(audio_path, language=None):  # pragma: no cover
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
    # Whole-file diarize gives globally-consistent speaker ids (no per-chunk relabeling), so
    # we do NOT chunk this — we just make the large upload robust. The big multipart POST can
    # throw a transient SSL EOF / transport error; retry it rather than falling back to chopping
    # (which would fragment speaker identities across pieces).
    import ssl, time
    d = None
    for attempt in range(4):
        req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=body, headers={
            "xi-api-key": _key("ELEVENLABS_API_KEY"),
            "Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
            break
        except (urllib.error.URLError, ssl.SSLError) as e:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))            # transient large-upload failure → retry
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


def gemini_read(audio_path, language=None, context=None):  # pragma: no cover
    """Gemini (multimodal LLM) — a 4th independent witness, different family again.
    Strong on accented/bilingual speech because it reasons over context, not just acoustics.
    `context`: optional priming for a focused re-listen (candidate words, neighbor words, domain
    vocabulary) — the model PROPOSES with better context; the deterministic vote still decides."""
    import base64, mimetypes
    audio = base64.b64encode(open(audio_path, "rb").read()).decode()
    ctype = mimetypes.guess_type(audio_path)[0] or "audio/mpeg"
    if language and language.lower() not in ("ja", "jpn", "japanese"):
        instr = ("Transcribe this audio verbatim, exactly as spoken, in its original language. "
                 "Do not translate. Output only the transcript text.")
    else:
        instr = ("Transcribe this audio verbatim, exactly as spoken. Keep Japanese in Japanese "
                 "and English in English (do not translate). Output only the transcript text.")
    if context:
        instr += (" Context that may help you hear correctly (do NOT copy it blindly; "
                  "write only what the audio actually says): " + context)
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


def hf_read(audio_path, language=None, model="openai/whisper-large-v3", retries=4):  # pragma: no cover
    """Whisper-large-v3 via Hugging Face Inference Providers (free tier; multilingual,
    auto-detects language). A 5th witness — adds the Whisper family to the consensus.
    The legacy api-inference.huggingface.co host is dead; this uses the router endpoint.

    HF's serverless model goes COLD (503 'loading') and rate-limits bursts (429) — the
    real cause of the flaky empties, not audio length. So retry with backoff on the
    transient codes; raise on anything else. This is what lets chunked/parallel HF be
    reliable instead of dropping chunks silently."""
    import mimetypes, time
    ctype = mimetypes.guess_type(audio_path)[0] or "audio/wav"
    data = open(audio_path, "rb").read()
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(
            f"https://router.huggingface.co/hf-inference/models/{model}",
            data=data,
            headers={"Authorization": "Bearer " + _key("HF_API_KEY"), "Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r).get("text", "").strip()
        except urllib.error.HTTPError as e:
            if e.code in (503, 429, 500, 502) and attempt < retries - 1:
                time.sleep(delay); delay *= 2          # cold-start / throttle → back off
                continue
            raise
    return ""


def deepgram_structured(audio_path, language="en"):  # pragma: no cover
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


_WHISPER_LOCAL = None


def whisper_local(audio_path, language=None, model_size="large-v3"):  # pragma: no cover
    """Local Whisper via faster-whisper — a FREE, unlimited, all-language witness that runs on the
    M1 (no API, no credits, no rate limits). Replaces the HF Whisper witness that hit the 402 credit
    wall. Model is loaded once and cached. Returns '' if faster-whisper isn't installed."""
    global _WHISPER_LOCAL
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return ""
    if _WHISPER_LOCAL is None:
        _WHISPER_LOCAL = WhisperModel(model_size, device="cpu", compute_type="int8")
    segs, _ = _WHISPER_LOCAL.transcribe(audio_path, language=language or None, beam_size=1)
    return " ".join(s.text for s in segs).strip()


def whisper_detect_language(audio_path):  # pragma: no cover
    """Free local-Whisper language id — the second detector that cross-checks Deepgram's, so one
    detector can't misroute the whole job. Returns an ISO-639-1 code, or '' if unavailable."""
    global _WHISPER_LOCAL
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return ""
    if _WHISPER_LOCAL is None:
        _WHISPER_LOCAL = WhisperModel("large-v3", device="cpu", compute_type="int8")
    try:
        _, info = _WHISPER_LOCAL.transcribe(audio_path, beam_size=1)
        return getattr(info, "language", "") or ""
    except Exception:
        return ""


# ISO 639-1 (our codes) -> 639-3 (what MMS / Seamless want)
_ISO3 = {"en": "eng", "vi": "vie", "ar": "arb", "hi": "hin", "ur": "urd", "fr": "fra", "de": "deu",
         "pt": "por", "tr": "tur", "es": "spa", "ru": "rus", "uk": "ukr", "ja": "jpn", "ko": "kor"}


def _load_wav16(path):
    """Load audio as a 16 kHz mono float array (chunks already are; whole files via ffmpeg)."""
    import soundfile as sf
    try:
        wav, sr = sf.read(path)
        if sr == 16000 and getattr(wav, "ndim", 1) == 1:
            return wav
    except Exception:
        pass
    import subprocess, tempfile, os
    fd, tmp = tempfile.mkstemp(suffix=".wav"); os.close(fd)
    subprocess.run(["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "16000", tmp, "-loglevel", "error"], check=True)
    wav, _ = sf.read(tmp); os.remove(tmp)
    return wav


_MMS = {}


def mms_local(audio_path, language=None):  # pragma: no cover
    """Meta MMS (facebook/mms-1b-all) — free local ASR for 1000+ languages; strongest value on the
    hard/thin-roster languages (ar/hi/ur). Loads the per-language adapter. Returns '' on any failure."""
    lang3 = _ISO3.get((language or "en").split("-")[0], "eng")
    try:
        import torch
        from transformers import Wav2Vec2ForCTC, AutoProcessor
    except Exception:
        return ""
    if "model" not in _MMS:
        try:
            _MMS["proc"] = AutoProcessor.from_pretrained("facebook/mms-1b-all")
            _MMS["model"] = Wav2Vec2ForCTC.from_pretrained("facebook/mms-1b-all")
        except Exception:
            return ""
    proc, model = _MMS["proc"], _MMS["model"]
    try:
        proc.tokenizer.set_target_lang(lang3)
        model.load_adapter(lang3)
        wav = _load_wav16(audio_path)
        inp = proc(wav, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            ids = torch.argmax(model(**inp).logits, dim=-1)
        return proc.decode(ids[0]).strip()
    except Exception:
        return ""


_PHOWHISPER = None


def phowhisper_local(audio_path, language=None):  # pragma: no cover
    """PhoWhisper (vinai/PhoWhisper-large) — Vietnamese-specialized Whisper. Free, local. Returns ''."""
    global _PHOWHISPER
    try:
        from transformers import pipeline
    except Exception:
        return ""
    if _PHOWHISPER is None:
        try:
            _PHOWHISPER = pipeline("automatic-speech-recognition", model="vinai/PhoWhisper-large",
                                   chunk_length_s=30)
        except Exception:
            return ""
    try:
        r = _PHOWHISPER(audio_path)
        return (r.get("text", "") if isinstance(r, dict) else str(r)).strip()
    except Exception:
        return ""


_SEAMLESS = {}


def seamless_local(audio_path, language=None):  # pragma: no cover
    """Meta SeamlessM4T v2 (facebook/seamless-m4t-v2-large) — multilingual ASR (and the engine for the
    future EN<->X translation track). Heavy (~9GB); free, local. Returns '' on any failure."""
    lang3 = _ISO3.get((language or "en").split("-")[0], "eng")
    try:
        import torch
        from transformers import AutoProcessor, SeamlessM4Tv2Model
    except Exception:
        return ""
    if "model" not in _SEAMLESS:
        try:
            _SEAMLESS["proc"] = AutoProcessor.from_pretrained("facebook/seamless-m4t-v2-large")
            _SEAMLESS["model"] = SeamlessM4Tv2Model.from_pretrained("facebook/seamless-m4t-v2-large")
        except Exception:
            return ""
    proc, model = _SEAMLESS["proc"], _SEAMLESS["model"]
    try:
        import torch
        wav = _load_wav16(audio_path)
        inp = proc(audio=wav, sampling_rate=16000, return_tensors="pt")   # 'audio' (audios deprecated)
        with torch.no_grad():
            out = model.generate(**inp, tgt_lang=lang3, generate_speech=False)
        seq = out[0] if torch.is_tensor(out) else out.sequences
        return proc.decode(seq[0] if seq.ndim > 1 else seq, skip_special_tokens=True).strip()
    except Exception:
        return ""


_PYANNOTE = None


def pyannote_diarize(audio_path, language=None):  # pragma: no cover
    """pyannote.audio speaker diarization — a 3rd INDEPENDENT diarizer (embedding-based, local, free).
    Different family than Deepgram/Scribe, so it strengthens cross-diarizer consensus and is the
    voice-fingerprint backstop for very long audio. Returns [{start,end,speaker,text=''}] (diarization
    only — no ASR). Uses HF_TOKEN; returns [] if pyannote/token unavailable."""
    global _PYANNOTE
    try:
        from pyannote.audio import Pipeline
    except Exception:
        return []
    if _PYANNOTE is None:
        try:
            tok = _key("HF_TOKEN")
        except Exception:
            return []
        try:
            _PYANNOTE = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=tok)
        except TypeError:
            _PYANNOTE = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=tok)
    out = _PYANNOTE(audio_path)
    ann = getattr(out, "speaker_diarization", out)   # pyannote 4.x wraps it in DiarizeOutput
    return [{"start": float(seg.start), "end": float(seg.end), "speaker": spk, "text": ""}
            for seg, _, spk in ann.itertracks(yield_label=True)]


def deepgram_detect_language(audio_path):  # pragma: no cover
    """Deepgram language auto-detection — returns the detected language code (e.g. 'en', 'ja',
    'ru') or '' if undetermined. Cheap front-end so the router can pick the right roster/profile
    without the caller specifying a language."""
    url = "https://api.deepgram.com/v1/listen?model=nova-2&detect_language=true&punctuate=false"
    req = urllib.request.Request(url, data=open(audio_path, "rb").read(), headers={
        "Authorization": "Token " + _key("DEEPGRAM_API_KEY"), "Content-Type": "audio/wav"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    ch = d.get("results", {}).get("channels", [{}])[0]
    lang = ch.get("detected_language") or ""
    if not lang:
        alts = ch.get("alternatives", [{}])
        lang = alts[0].get("languages", [""])[0] if alts else ""
    return lang.split("-")[0].lower() if lang else ""    # 'en-US' -> 'en'


def deepgram_read(audio_path, language="ja"):  # pragma: no cover
    """Deepgram Nova — backup witness (weaker on bilingual audio; use for clean speech)."""
    url = f"https://api.deepgram.com/v1/listen?model=nova-3&language={language}&smart_format=true"
    req = urllib.request.Request(url, data=open(audio_path, "rb").read(), headers={
        "Authorization": "Token " + _key("DEEPGRAM_API_KEY"), "Content-Type": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return d["results"]["channels"][0]["alternatives"][0]["transcript"].strip()


def gemini_video_read(video_path, language=None):  # pragma: no cover
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
