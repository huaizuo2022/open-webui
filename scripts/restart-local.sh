#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8081}"
HOST="${HOST:-127.0.0.1}"
LOG_DIR="${ROOT_DIR}/.runlogs"
LOG_FILE="${LOG_DIR}/open-webui-${PORT}.log"
HEALTH_URL="http://${HOST}:${PORT}/api/version"
UVICORN_CMD=(
  .venv/bin/uvicorn
  open_webui.main:app
  --app-dir backend
  --host "$HOST"
  --port "$PORT"
  --forwarded-allow-ips "*"
)

mkdir -p "$LOG_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing virtualenv at .venv" >&2
  exit 1
fi

if [[ ! -d "node_modules" ]]; then
  echo "Missing node_modules. Run npm install first." >&2
  exit 1
fi

echo "[1/4] Building frontend..."
npm run build

echo "[2/4] Stopping existing backend on port ${PORT}..."
if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  kill "$(lsof -tiTCP:"$PORT" -sTCP:LISTEN)"
  sleep 1
fi

echo "[3/4] Starting backend..."
nohup "${UVICORN_CMD[@]}" >"$LOG_FILE" 2>&1 &
NEW_PID=$!

echo "[4/4] Waiting for health check..."
for _ in $(seq 1 30); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Restart complete."
    echo "PID: $NEW_PID"
    echo "Health: $HEALTH_URL"
    echo "Log: $LOG_FILE"
    exit 0
  fi
  sleep 1
done

echo "Backend failed to become healthy. Tail of log:" >&2
tail -n 80 "$LOG_FILE" >&2 || true
exit 1
