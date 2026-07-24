#!/usr/bin/env bash
# One-command setup on a fresh machine (Mac, Linux, or Windows-via-WSL).
#
#   git clone https://github.com/Alexander-Sorrell-IT/transcript-truth.git
#   cd transcript-truth
#   bash setup.sh              # core engine: deps + data + keys template + self-test
#   bash setup.sh --models     # ALSO install the free local model tier (several GB; recommended)
#
# CPU-only boxes are fully supported: local Whisper = faster-whisper int8 (no GPU; RAM is the
# only requirement, 16GB+ fine, 64GB ideal). Apple Silicon auto-uses mlx-whisper instead.
set -e
cd "$(dirname "$0")"

echo "==> [1/5] Checking prerequisites ..."
command -v python3 >/dev/null || { echo "python3 is required (3.10+). Install it first."; exit 1; }
python3 - <<'PY'
import sys; assert sys.version_info >= (3, 10), f"need Python 3.10+, found {sys.version.split()[0]}"
print(f"   [ok] Python {sys.version.split()[0]}")
PY
if command -v ffmpeg >/dev/null; then echo "   [ok] ffmpeg"; else
  echo "   [!!] ffmpeg missing — chunking/slow-listen/earcheck need it."
  echo "        mac: brew install ffmpeg   debian/ubuntu/WSL: sudo apt install ffmpeg"
fi

echo "==> [2/5] Installing core Python deps ..."
pip3 install -q -r requirements.txt

echo "==> [3/5] Keys ..."
if [ ! -f .env ]; then cp .env.example .env; echo "   created .env — paste your API keys into it"; \
else echo "   [ok] .env exists"; fi

echo "==> [4/5] Reference data ..."
# ja core data (JMdict-common 16MB + 954k-name JMnedict surfaces) ships IN the repo, so Japanese
# works straight after clone; this fetches the optional FULL JMdict (117MB, better word coverage).
python3 scripts/fetch_data.py || echo "   (full JMdict fetch failed — engine falls back to the bundled common dictionary)"

if [ "$1" = "--models" ]; then
  echo "==> [4b] Local model tier (free witnesses, several GB) ..."
  pip3 install -q -r requirements-models.txt
  bash setup_models.sh || true
fi

echo "==> [5/5] Self-test (full deterministic suite, offline) ..."
python3 -m pytest tests/ -q

echo
echo "READY. Quick use:"
echo "  ./check transcript.txt              # QA a finished transcript (auto ja/en, GoTranscript rules)"
echo "  ./check transcript.txt --ship       # HARD GATE: refuses while any ⚠/unresolved span remains"
echo "  ./earcheck draft.md audio.mp3       # ear-verify each flagged span, one keypress per span"
echo "  python3 -m transcript_truth.cli f.txt --profile=ja --site=gotranscript"
