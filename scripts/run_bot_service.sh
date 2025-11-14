#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

LOG_DIR="$REPO_DIR/logs"
SUPERVISOR_LOG="$LOG_DIR/bot-service.log"
PID_FILE="$REPO_DIR/bot-service.pid"

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
    if kill -0 "$(cat "$PID_FILE")" >/dev/null 2>&1; then
        echo "GuildScout bot service is already running (PID $(cat "$PID_FILE"))."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

if [[ ! -x "$REPO_DIR/.venv/bin/python" ]]; then
    echo "Virtual environment not found. Please run 'python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt'"
    exit 1
fi

source "$REPO_DIR/.venv/bin/activate"
echo $$ > "$PID_FILE"

cleanup() {
    rm -f "$PID_FILE"
}
trap cleanup EXIT

echo "$(date '+%Y-%m-%d %H:%M:%S') - GuildScout supervisor started (PID $$)" >> "$SUPERVISOR_LOG"

while true; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting GuildScout bot..." >> "$SUPERVISOR_LOG"
    set +e
    python run.py >> "$SUPERVISOR_LOG" 2>&1
    EXIT_CODE=$?
    set -e
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Bot exited with code $EXIT_CODE. Restarting in 5s..." >> "$SUPERVISOR_LOG"
    sleep 5
done
