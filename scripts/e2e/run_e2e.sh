#!/usr/bin/env bash
# Start the langgraph server from THIS worktree (auth enabled), run the e2e
# auth/RLS isolation driver against it, then tear the server down.
set -uo pipefail

PORT="${PORT:-2030}"
READINESS_ATTEMPTS="${READINESS_ATTEMPTS:-90}"
READINESS_CURL_MAX_TIME="${READINESS_CURL_MAX_TIME:-2}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="${LOG:-/tmp/lg_rls_${PORT}.log}"
URL="http://127.0.0.1:${PORT}"

cd "$ROOT" || exit 2

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Choose another port, for example:"
  echo "  PORT=2031 scripts/e2e/run_e2e.sh"
  exit 2
fi

echo "Starting langgraph dev on $PORT (log: $LOG)"
uv run langgraph dev --no-browser --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 &
SERVER_PID=$!

cleanup() {
  echo "Stopping server (pid $SERVER_PID + children)"
  pkill -P "$SERVER_PID" 2>/dev/null
  kill "$SERVER_PID" 2>/dev/null
}
trap cleanup EXIT

echo -n "Waiting for /docs"
ready=""
for _ in $(seq 1 "$READINESS_ATTEMPTS"); do
  code=$(curl --max-time "$READINESS_CURL_MAX_TIME" -s -o /dev/null -w '%{http_code}' "$URL/docs" 2>/dev/null)
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

echo "=== Running scripts/e2e/e2e_auth.py ==="
SERVER_URL="$URL" uv run python scripts/e2e/e2e_auth.py
RC=$?

if [ "$RC" -ne 0 ]; then
  echo "=== server log tail (e2e failed) ==="
  tail -40 "$LOG"
fi
exit "$RC"
