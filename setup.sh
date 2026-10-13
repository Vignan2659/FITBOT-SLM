#!/bin/bash
# One-time FitBot setup on macOS (Apple Silicon). Safe to run again: finished steps are skipped.
#   bash setup.sh
set -e
cd "$(dirname "$0")"

step() { printf "\n\033[1;36m==> %s\033[0m\n" "$1"; }

step "Checking Python"
PY=""
for c in python3.12 python3.11 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /opt/homebrew/bin/python3.12; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.12 (or 3.11) not found. Install it from https://www.python.org/downloads/ or with: brew install python@3.12"
  exit 1
fi
echo "Using $PY ($($PY --version))"

if [ ! -x .venv/bin/python ]; then
  step "Creating the Python environment (.venv)"
  "$PY" -m venv .venv
fi
step "Installing Python packages (first time: several minutes)"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements-lock.txt
.venv/bin/python -c "import torch; print('PyTorch', torch.__version__, '| Apple GPU (MPS):', torch.backends.mps.is_available())"

if [ ! -f backend/.env ]; then
  step "Creating backend/.env"
  cp backend/.env.example backend/.env
  SECRET=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))")
  sed -i '' "s|^JWT_SECRET=.*|JWT_SECRET=$SECRET|" backend/.env
fi

if [ ! -f frontend/dist/index.html ]; then
  step "Building the web app"
  if command -v npm >/dev/null 2>&1; then
    (cd frontend && npm install --silent && npm run build)
  else
    echo "Node.js not found - install it from https://nodejs.org (LTS) or with: brew install node, then run setup.sh again."
    exit 1
  fi
fi

step "Installing the fine-tuned FitBot 4B model"
.venv/bin/python scripts/setup_model.py

step "Done. Start FitBot with:  bash start.sh   (or double-click FitBot.command)"
