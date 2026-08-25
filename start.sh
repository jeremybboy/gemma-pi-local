#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  DEFAULT_APP_HOST="127.0.0.1"
else
  DEFAULT_APP_HOST="0.0.0.0"
fi

APP_HOST="${GEMMA_PI_HOST:-${DEFAULT_APP_HOST}}"
APP_PORT="${GEMMA_PI_PORT:-8080}"
LITERT_HOST="${GEMMA_PI_LITERT_HOST:-127.0.0.1}"
LITERT_PORT="${GEMMA_PI_LITERT_PORT:-9379}"
MODEL_ID="${GEMMA_PI_MODEL:-gemma4-e4b}"
LITERT_PID=""
APP_PID=""

fail() {
  echo "Error: $*" >&2
  exit 1
}

port_open() {
  "${VENV_DIR}/bin/python" - "$1" "$2" <<'PY'
import socket
import sys

host, port = sys.argv[1], int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=0.3):
        pass
except OSError:
    raise SystemExit(1)
PY
}

cleanup() {
  trap - EXIT INT TERM
  [[ -n "${APP_PID}" ]] && kill "${APP_PID}" 2>/dev/null || true
  [[ -n "${LITERT_PID}" ]] && kill "${LITERT_PID}" 2>/dev/null || true
  [[ -n "${APP_PID}" ]] && wait "${APP_PID}" 2>/dev/null || true
  [[ -n "${LITERT_PID}" ]] && wait "${LITERT_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

[[ -x "${VENV_DIR}/bin/litert-lm" ]] || fail "Run the installer for your platform first."
[[ -x "${VENV_DIR}/bin/uvicorn" ]] || fail "Run the installer for your platform first."

if ! "${VENV_DIR}/bin/litert-lm" list 2>/dev/null | awk -v model="${MODEL_ID}" '$1 == model {found=1} END {exit !found}'; then
  fail "Model ${MODEL_ID} is not imported. Re-run the installer for your platform."
fi
if port_open "${LITERT_HOST}" "${LITERT_PORT}"; then
  fail "Port ${LITERT_PORT} is already in use."
fi
if port_open "127.0.0.1" "${APP_PORT}"; then
  fail "Port ${APP_PORT} is already in use."
fi

export GEMMA_PI_LITERT_URL="http://${LITERT_HOST}:${LITERT_PORT}/v1"
export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

echo "Starting LiteRT-LM on ${LITERT_HOST}:${LITERT_PORT}..."
"${VENV_DIR}/bin/litert-lm" serve --host "${LITERT_HOST}" --port "${LITERT_PORT}" &
LITERT_PID=$!

READY=0
for _ in $(seq 1 120); do
  if port_open "${LITERT_HOST}" "${LITERT_PORT}"; then
    READY=1
    break
  fi
  if ! kill -0 "${LITERT_PID}" 2>/dev/null; then
    fail "LiteRT-LM stopped during startup."
  fi
  sleep 1
done
[[ "${READY}" == "1" ]] || fail "LiteRT-LM did not become ready within 120 seconds."

echo "Starting Gemma Pi Local on ${APP_HOST}:${APP_PORT}..."
"${VENV_DIR}/bin/uvicorn" app.main:app --host "${APP_HOST}" --port "${APP_PORT}" &
APP_PID=$!

echo "Gemma Pi Local is running."
if [[ "${APP_HOST}" == "127.0.0.1" || "${APP_HOST}" == "localhost" ]]; then
  echo "Open http://127.0.0.1:${APP_PORT} on this computer."
else
  DISPLAY_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "${DISPLAY_HOST}" ]] || DISPLAY_HOST="${APP_HOST}"
  echo "Open http://${DISPLAY_HOST}:${APP_PORT} from the trusted LAN."
fi
wait "${APP_PID}"
