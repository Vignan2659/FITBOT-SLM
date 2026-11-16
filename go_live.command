#!/bin/bash
# Put FitBot online from this Mac: starts FitBot (production mode) and an ngrok tunnel on your free ngrok address.
# Double-click this file. Keep the window open and the Mac on; close the window or press Ctrl+C to go offline.
cd "$(dirname "$0")" || exit 1

NGROK=$(command -v ngrok || ls /opt/homebrew/bin/ngrok /usr/local/bin/ngrok release/ngrok 2>/dev/null | head -1)
if [ -z "$NGROK" ]; then
  echo "ngrok is not installed. Install it from https://dashboard.ngrok.com/get-started/setup/macos and run this again."
  read -r -p "Press Return to close."; exit 1
fi
CONF=$("$NGROK" config check 2>/dev/null | grep -o '/.*\.yml')
if [ -z "$CONF" ] || ! grep -q "authtoken:" "$CONF" 2>/dev/null; then
  echo "ngrok has no authtoken yet. Copy the 'ngrok config add-authtoken ...' command from"
  echo "https://dashboard.ngrok.com/get-started/your-authtoken, run it in Terminal, then run this again."
  read -r -p "Press Return to close."; exit 1
fi

cleanup() {
  echo; echo "Taking FitBot offline..."
  [ -n "$TUNNEL" ] && kill "$TUNNEL" 2>/dev/null
  [ -n "$AWAKE" ] && kill "$AWAKE" 2>/dev/null
  lsof -ti:8000 | xargs kill 2>/dev/null
  rm -f release/public_url.txt
}
trap cleanup EXIT INT TERM

mkdir -p release
echo "Starting FitBot (the model takes up to a minute to load)..."
ENVIRONMENT=production bash start.sh > release/live_server.log 2>&1 &
for i in $(seq 1 150); do curl -s 127.0.0.1:8000/health | grep -q '"status":"ok"' && break; sleep 2; done
if ! curl -s 127.0.0.1:8000/health | grep -q '"status":"ok"'; then
  echo "FitBot did not start. The last lines of release/live_server.log:"; tail -15 release/live_server.log
  read -r -p "Press Return to close."; exit 1
fi

caffeinate -dimsu &                        # keep the Mac awake while FitBot is online
AWAKE=$!
"$NGROK" http 8000 --log stdout --log-level warn > release/live_tunnel.log 2>&1 &
TUNNEL=$!
URL=""
for i in $(seq 1 30); do
  URL=$(curl -s 127.0.0.1:4040/api/tunnels | python3 -c 'import sys,json
try: print(next(t["public_url"] for t in json.load(sys.stdin)["tunnels"] if t["public_url"].startswith("https")))
except Exception: pass')
  [ -n "$URL" ] && break; sleep 1
done
if [ -z "$URL" ]; then
  echo "The ngrok tunnel did not start:"; tail -15 release/live_tunnel.log
  read -r -p "Press Return to close."; exit 1
fi
echo "$URL" > release/public_url.txt
echo
echo "  FitBot is live at:  $URL"
echo
echo "  Share that link. Visitors see an ngrok notice once and click Visit."
echo "  Keep this window open and the Mac on. Close it or press Ctrl+C to go offline."
wait "$TUNNEL"
