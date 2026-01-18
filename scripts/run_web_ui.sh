#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${WEB_UI_PORT:-8090}"

exec uvicorn web_api.app:app --host 0.0.0.0 --port "$PORT"
