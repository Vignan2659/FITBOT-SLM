#!/bin/bash
# Double-click in Finder to start FitBot (runs the one-time setup first if needed).
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ] || [ ! -f models/fitbot-qwen3-4b/merged/config.json ] || [ ! -f frontend/dist/index.html ]; then
  bash setup.sh || { read -r -p "Setup failed - press Enter to close"; exit 1; }
fi
(sleep 45; open http://127.0.0.1:8000) &
bash start.sh
