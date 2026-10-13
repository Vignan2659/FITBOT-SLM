#!/bin/bash
# Renders the FitBot launch film end to end (about 10-15 minutes). Double-click in Finder, or: bash marketing/launch/make_film.command
cd "$(dirname "$0")/../.." || exit 1
ROOT="$PWD"; PY="$ROOT/.venv/bin/python"; LOG="$ROOT/marketing/launch/build/make_film.log"
mkdir -p marketing/launch/build; : > "$LOG"
exec > >(tee -a "$LOG") 2>&1
echo "== FitBot film $(date)"
"$PY" -m playwright install chromium >/dev/null 2>&1 && echo "chromium ok"
echo "(re)starting FitBot server with the current code..."; (bash start.sh > marketing/launch/build/server.log 2>&1 &)
sleep 5
for i in $(seq 1 60); do curl -fs http://127.0.0.1:8000/health | grep -q '"status":"ok"' && break; sleep 3; done
curl -fs http://127.0.0.1:8000/health | head -c 200; echo
cd marketing/launch || exit 1
echo "== STEP tts-env (neural voice, separate environment; falls back to macOS voices if it fails)"
if [ ! -x .venv-tts/bin/python ]; then
  PY312=$(command -v python3.12 || echo /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12)
  "$PY312" -m venv .venv-tts && .venv-tts/bin/pip install -q --upgrade pip \
    && .venv-tts/bin/pip install -q "kokoro>=0.9.4" soundfile "misaki[en]" \
    || { echo "kokoro install failed - using macOS voice"; rm -rf .venv-tts; }
fi
if [ -x .venv-tts/bin/python ]; then
  echo '[{"text":"FitBot, presented by Veltris.","out":"build/kokoro_test.wav"}]' > build/kokoro_test.json
  .venv-tts/bin/python tts_kokoro.py build/kokoro_test.json || { echo "kokoro test failed - using macOS voice"; rm -rf .venv-tts; }
fi
echo "== STEP collect"; "$PY" collect.py || { echo "FAILED collect"; exit 1; }
echo "== STEP voice";   "$PY" voice.py "$@" || { echo "FAILED voice"; exit 1; }
echo "== STEP music";   "$PY" music.py || { echo "FAILED music"; exit 1; }
echo "== STEP stills";  "$PY" -c "import json;tl=json.load(open('build/timeline.json'));print(','.join(str(round((s['start']+s['end'])/2,1)) for s in tl['scenes']))" > build/still_times.txt
"$PY" build.py --stills "$(cat build/still_times.txt)" --tag v2 || { echo "FAILED stills"; exit 1; }
echo "== STEP render";  "$PY" build.py || { echo "FAILED render"; exit 1; }
FF=$("$PY" -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
echo "== STEP small";   "$FF" -y -loglevel error -i "$ROOT/marketing/FitBot_v2_Launch.mp4" -vf scale=1280:-2 -c:v libx264 -preset slow -crf 27 -c:a aac -b:a 128k -movflags +faststart "$ROOT/marketing/FitBot_v2_Launch_small.mp4"
ls -la "$ROOT"/marketing/FitBot_v2_Launch*.mp4
echo "== ALL DONE"
