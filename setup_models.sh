#!/usr/bin/env bash
# One-command model setup for transcript-truth.
#   bash setup_models.sh          # install deps + download all free/local models
#   bash setup_models.sh --keys   # also open the pages for models needing a manual API key/license
#
# Free/local models are installed and cached automatically. The few that need YOUR account
# (pyannote license + HF token, NVIDIA ASR) are listed at the end and opened with --keys.

echo "==> [1/3] Installing Python packages (free, local) ..."
pip3 install -q \
  faster-whisper silero-vad kiwipiepy zeyrek stanza \
  transformers torch sentencepiece soundfile huggingface_hub \
  pyannote.audio camel-tools \
  || echo "   (some packages may already be installed)"

echo "==> [2/3] Pre-downloading open models (cached to ~/.cache; safe to re-run) ..."
python3 - <<'PY'
def ok(d):  print(f"   [ok]   {d}")
def skip(d, e): print(f"   [skip] {d}: {str(e)[:60]}")

try:
    from faster_whisper import WhisperModel; WhisperModel("large-v3", device="cpu", compute_type="int8"); ok("local Whisper large-v3")
except Exception as e: skip("local Whisper", e)
try:
    from silero_vad import load_silero_vad; load_silero_vad(); ok("Silero VAD")
except Exception as e: skip("Silero VAD", e)
try:
    import stanza
    for lg in ["en","fr","de","pt","tr","ru","uk","ar","hi","ko","ja","vi"]:
        try: stanza.download(lg, verbose=False); ok(f"Stanza {lg}")
        except Exception as e: skip(f"Stanza {lg}", e)
except Exception as e: skip("Stanza", e)

# Open ASR models via HF snapshot (no auth needed). Sizes noted; ~15GB total.
from_hub = [
    ("vinai/PhoWhisper-large",        "PhoWhisper (Vietnamese, ~3GB)"),
    ("facebook/mms-1b-all",           "Meta MMS (1000+ langs, ~3GB)"),
    ("facebook/seamless-m4t-v2-large","Meta Seamless (ASR+translation, ~9GB)"),
]
try:
    from huggingface_hub import snapshot_download
    for repo, desc in from_hub:
        try: snapshot_download(repo); ok(desc)
        except Exception as e: skip(desc, e)
except Exception as e: skip("huggingface_hub", e)

# CAMeL Tools Arabic data
try:
    import subprocess; subprocess.run(["camel_data","-i","light"], check=False); ok("CAMeL Tools (Arabic) data")
except Exception as e: skip("CAMeL data", e)
PY

echo "==> [3/3] Models needing YOUR account:"
cat <<'EOF'
   - pyannote (diarization / voice-fingerprint): accept the license on its HF page (logged in),
     then create a HF READ token and add to .env:   HF_TOKEN=hf_xxxxx
   - NVIDIA Parakeet/Canary: choose local NeMo (free, heavy) or the build.nvidia.com API.
EOF

if [ "$1" = "--keys" ]; then
  echo "   opening the pages ..."
  open "https://huggingface.co/pyannote/speaker-diarization-3.1"
  open "https://huggingface.co/settings/tokens"
  open "https://build.nvidia.com/explore/speech"
fi
echo "==> done."
