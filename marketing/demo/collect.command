#!/bin/bash
# Re-collects only the real answers and screenshots (starts FitBot if it is not running, stops it again after).
cd "$(dirname "$0")/../.." || exit 1
LOG=marketing/demo/build/collect.log; mkdir -p marketing/demo/build; : > $LOG
{
STARTED=0
if ! curl -fs 127.0.0.1:8000/health >/dev/null; then
  (bash start.sh > marketing/demo/build/server.log 2>&1 &); STARTED=1
  for i in $(seq 1 120); do curl -fs 127.0.0.1:8000/health | grep -q '"status":"ok"' && break; sleep 2; done
fi
.venv/bin/python marketing/demo/collect_demo.py || echo "FAILED collect"
[ $STARTED = 1 ] && lsof -ti:8000 | xargs kill 2>/dev/null
echo COLLECT-CMD-DONE
} >> $LOG 2>&1
