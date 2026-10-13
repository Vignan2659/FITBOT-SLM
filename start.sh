#!/bin/bash
# Starts FitBot: the FastAPI backend also serves the web app. Open http://127.0.0.1:8000 once the log says
# "Application startup complete" (the 4B model takes ~20-60 s to load). Press Ctrl+C to stop.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ] || [ ! -f models/fitbot-qwen3-4b/merged/config.json ]; then
  echo "FitBot is not set up yet - run:  bash setup.sh"; exit 1
fi
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "Port 8000 is in use - stopping the old FitBot server"; lsof -ti:8000 | xargs kill; sleep 2
fi
cd backend || exit 1
export PYTORCH_ENABLE_MPS_FALLBACK=1   # run any operation the Apple GPU lacks on the CPU instead of failing
exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
