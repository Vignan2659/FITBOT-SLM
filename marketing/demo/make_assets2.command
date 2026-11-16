#!/bin/bash
# Records the new voice-over and collects the workout tracking material for the demo film.
cd "$(dirname "$0")/../.." || exit 1
LOG=marketing/demo/build/assets2.log; mkdir -p marketing/demo/build/vo; : > $LOG
{
STARTED=0
if ! curl -fs 127.0.0.1:8000/health >/dev/null; then
  (bash start.sh > marketing/demo/build/server.log 2>&1 &); STARTED=1
  for i in $(seq 1 120); do curl -fs 127.0.0.1:8000/health | grep -q '"status":"ok"' && break; sleep 2; done
fi
(cd marketing/demo && ../../.venv/bin/python collect_extra.py) || echo "FAILED extra"
[ $STARTED = 1 ] && lsof -ti:8000 | xargs kill 2>/dev/null
cd marketing/demo || exit 1
rm -f build/vo/*.wav
FITBOT_KOKORO_VOICE=af_heart FITBOT_KOKORO_SPEED=1.0 ../launch/.venv-tts/bin/python ../launch/tts_kokoro.py vo_jobs.json || echo "FAILED voice"
ls build/vo | wc -l
echo ASSETS2-DONE
} >> $LOG 2>&1
