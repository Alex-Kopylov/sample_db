#!/usr/bin/env bash
# Start the langgraph server from THIS worktree (auth enabled), run the e2e
# auth/RLS isolation driver against it, then tear the server down.
set -uo pipefail

PORT="${PORT:-2030}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="/tmp/lg_rls.log"
URL="http://127.0.0.1:${PORT}"

cd "$ROOT" || exit 2

# Free the port if a stale server holds it.
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT busy; killing stale listener"
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t | xargs -r kill
  sleep 2
fi

echo "Starting langgraph dev on $PORT (log: $LOG)"
uv run langgraph dev --no-browser --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 &
SERVER_PID=$!

cleanup() {
  echo "Stopping server (pid $SERVER_PID + children)"
  pkill -P "$SERVER_PID" 2>/dev/null
  kill "$SERVER_PID" 2>/dev/null
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | xargs -r kill 2>/dev/null
}
trap cleanup EXIT

echo -n "Waiting for /docs"
ready=""
for _ in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL/docs" 2>/dev/null)
  if [ "$code" = "200" ]; then ready=1; echo " ready"; break; fi
  echo -n "."
  sleep 1
done
if [ -z "$ready" ]; then
  echo " TIMEOUT"
  echo "=== server log tail ==="
  tail -40 "$LOG"
  exit 3
fi

echo "=== Running e2e_auth.py ==="
SERVER_URL="$URL" uv run python e2e_auth.py
RC=$?

if [ "$RC" -ne 0 ]; then
  echo "=== server log tail (e2e failed) ==="
  tail -40 "$LOG"
fi
exit "$RC"
