#!/bin/bash
# Collects real FitBot answers and screenshots and records the voice-over for the demo film.
cd "$(dirname "$0")/../.." || exit 1
ROOT="$PWD"; LOG="$ROOT/marketing/demo/build/assets.log"
mkdir -p marketing/demo/build/vo; : > "$LOG"
exec > >(tee -a "$LOG") 2>&1
curl -fs http://127.0.0.1:8000/health | head -c 120; echo
.venv/bin/python marketing/demo/collect_demo.py || echo "FAILED collect"
cd marketing/demo || exit 1
FITBOT_KOKORO_VOICE=af_heart FITBOT_KOKORO_SPEED=0.98 ../launch/.venv-tts/bin/python ../launch/tts_kokoro.py vo_jobs.json || echo "FAILED voice"
ls build/vo | wc -l
echo ASSETS-DONE
