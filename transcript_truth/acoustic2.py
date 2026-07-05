"""Independent acoustic witness: a SECOND ASR of a different family (wav2vec2 XLSR-CTC,
not Whisper). Re-reads the same audio; where it disagrees with Whisper, that's a real
uncertainty no single model can self-detect. Closes the correlated blind spot —
two different acoustic models don't make the identical mistake.
"""
import functools

# per-language XLSR-CTC fine-tunes (same family, different heads). Independent of every
# Whisper AND of Deepgram/Scribe/Gemini — the second opinion languages with weak cloud
# support (Arabic) need most.
_MODELS = {
    "ja": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
    "ar": "jonatasgrosman/wav2vec2-large-xlsr-53-arabic",
    "fa": "jonatasgrosman/wav2vec2-large-xlsr-53-persian",
}


@functools.lru_cache(maxsize=2)
def _model(lang="ja"):
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    name = _MODELS.get(lang, _MODELS["ja"])
    proc = Wav2Vec2Processor.from_pretrained(name)
    mdl = Wav2Vec2ForCTC.from_pretrained(name)
    mdl.eval()
    return proc, mdl


def read(path, lang="ja"):
    """Independent wav2vec2 read of the audio (phonetic-level CTC)."""
    import torch, torchaudio
    proc, mdl = _model(lang)
    wav, sr = torchaudio.load(path)
    if wav.shape[0] > 1:
        wav = wav.mean(0, keepdim=True)
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    inp = proc(wav.squeeze().numpy(), sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        logits = mdl(inp.input_values).logits
    ids = torch.argmax(logits, dim=-1)
    text = proc.batch_decode(ids)[0]
    if lang in ("ar", "fa"):
        # XLSR-arabic emits full tashkeel (diacritics); transcripts are undiacritized —
        # strip harakat so the read votes on the same orthography as every other witness.
        import re
        text = re.sub("[ً-ْٰـ]", "", text)
    return text
