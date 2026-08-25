#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
MODEL_ID="${GEMMA_PI_MODEL:-gemma4-e4b}"
MODEL_REPO="${GEMMA_PI_MODEL_REPO:-litert-community/gemma-4-E4B-it-litert-lm}"
MODEL_FILE="${GEMMA_PI_MODEL_FILE:-gemma-4-E4B-it.litertlm}"

fail() {
  echo "Error: $*" >&2
  exit 1
}

echo "Gemma Pi Local macOS installer"
echo "Project: ${ROOT_DIR}"

[[ "$(uname -s)" == "Darwin" ]] || fail "This installer supports macOS only."
[[ "$(uname -m)" == "arm64" ]] || fail "The validated macOS profile requires Apple silicon (arm64)."

AVAILABLE_KB="$(df -Pk "${ROOT_DIR}" | awk 'NR == 2 {print $4}')"
if [[ -n "${AVAILABLE_KB}" && "${AVAILABLE_KB}" -lt 8388608 ]]; then
  fail "At least 8 GB of free disk is required for runtime and model import."
fi

PYTHON_BIN="${GEMMA_LOCAL_PYTHON:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3.13 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.13)"
  else
    fail "Python 3.13 is required. Install it with: brew install python@3.13"
  fi
fi
"${PYTHON_BIN}" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 13))' \
  || fail "GEMMA_LOCAL_PYTHON must point to Python 3.13."

if command -v docker >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1 && command -v brew >/dev/null 2>&1; then
  COMPOSE_PLUGIN="$(brew --prefix docker-compose 2>/dev/null)/lib/docker/cli-plugins/docker-compose"
  if [[ -x "${COMPOSE_PLUGIN}" ]]; then
    mkdir -p "${HOME}/.docker/cli-plugins"
    ln -sfn "${COMPOSE_PLUGIN}" "${HOME}/.docker/cli-plugins/docker-compose"
  fi
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1 || ! command -v colima >/dev/null 2>&1; then
  fail "Web search requires Docker CLI, Compose, and Colima. Install them with: brew install colima docker docker-compose"
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Creating Python 3.13 environment..."
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
elif ! "${VENV_DIR}/bin/python" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 13))'; then
  fail "Existing .venv does not use Python 3.13. Move it aside and rerun this installer."
fi

echo "Installing pinned macOS runtime and web dependencies..."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements-macos.txt"

if "${VENV_DIR}/bin/litert-lm" list 2>/dev/null | awk -v model="${MODEL_ID}" '$1 == model {found=1} END {exit !found}'; then
  echo "Model ${MODEL_ID} is already imported."
else
  echo "Importing ${MODEL_FILE} as ${MODEL_ID} (multi-gigabyte download)..."
  "${VENV_DIR}/bin/litert-lm" import \
    --from-huggingface-repo "${MODEL_REPO}" \
    "${MODEL_FILE}" \
    "${MODEL_ID}"
fi

mkdir -p "${HOME}/.local/bin"
ln -sfn "${ROOT_DIR}/bin/gemma-pi" "${HOME}/.local/bin/gemma-pi"
ln -sfn "${ROOT_DIR}/bin/gemma-pi" "${HOME}/.local/bin/gemma-local"

echo
echo "Installation complete."
echo "Start with: ${HOME}/.local/bin/gemma-local start"
echo "Then open:  http://127.0.0.1:8080"
if [[ ":${PATH}:" != *":${HOME}/.local/bin:"* ]]; then
  echo "Tip: add ${HOME}/.local/bin to PATH to run 'gemma-local' directly."
fi
