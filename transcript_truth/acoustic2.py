"""Independent acoustic witness: a SECOND ASR of a different family (wav2vec2 XLSR-CTC,
not Whisper). Re-reads the same audio; where it disagrees with Whisper, that's a real
uncertainty no single model can self-detect. Closes the correlated blind spot —
two different acoustic models don't make the identical mistake.
"""
import functools

_MODEL = "jonatasgrosman/wav2vec2-large-xlsr-53-japanese"


@functools.lru_cache(maxsize=1)
def _model():
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    proc = Wav2Vec2Processor.from_pretrained(_MODEL)
    mdl = Wav2Vec2ForCTC.from_pretrained(_MODEL)
    mdl.eval()
    return proc, mdl


def read(path):
    """Independent wav2vec2 read of the audio (kana/phonetic-level)."""
    import torch, torchaudio
    proc, mdl = _model()
    wav, sr = torchaudio.load(path)
    if wav.shape[0] > 1:
        wav = wav.mean(0, keepdim=True)
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    inp = proc(wav.squeeze().numpy(), sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        logits = mdl(inp.input_values).logits
    ids = torch.argmax(logits, dim=-1)
    return proc.batch_decode(ids)[0]
