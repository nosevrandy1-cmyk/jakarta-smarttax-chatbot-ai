#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV_BIN="${UV_BIN:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

echo "[backend] Starting FastAPI service on http://localhost:8000"
(
  cd "$ROOT_DIR/backend"
  "$UV_BIN" run uvicorn app.main:app --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!

trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM

echo "[frontend] Starting Next.js dev server on http://localhost:3000"
cd "$ROOT_DIR/frontend"
npm run dev
