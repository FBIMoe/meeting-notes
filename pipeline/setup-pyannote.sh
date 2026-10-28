#!/bin/zsh
# setup-pyannote.sh — optional, recommended: install pyannote for much better "who spoke when".
#
# Before running:
#   1. Make a free account at https://huggingface.co
#   2. Open https://huggingface.co/pyannote/speaker-diarization-community-1 and accept the terms
#   3. Settings → Access Tokens → create a READ token
# This script asks for the token once (stored by Hugging Face in ~/.cache/huggingface), downloads
# the model, and after that everything runs offline on your Mac.
set -eu
VENV="$HOME/.meeting-notes/pyannote-venv"
PY=$(command -v python3.13 || command -v python3.12 || true)
[[ -n "$PY" ]] || { print "Needs Python 3.12 or 3.13 (brew install python@3.13)"; exit 1; }

"$PY" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q pyannote.audio soundfile
"$VENV/bin/hf" auth whoami >/dev/null 2>&1 || "$VENV/bin/hf" auth login
"$VENV/bin/python" -c "from pyannote.audio import Pipeline; Pipeline.from_pretrained('pyannote/speaker-diarization-community-1'); print('pyannote ready')"
print "Set REDIARIZE=1 in ~/.meeting-notes/config.sh (it's the default)."
