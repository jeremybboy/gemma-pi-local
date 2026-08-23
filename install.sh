#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
MODEL_ID="${GEMMA_PI_MODEL:-gemma4-e4b}"
MODEL_REPO="${GEMMA_PI_MODEL_REPO:-litert-community/gemma-4-E4B-it-litert-lm}"
MODEL_FILE="${GEMMA_PI_MODEL_FILE:-gemma-4-E4B-it.litertlm}"
ALLOW_UNSUPPORTED="${GEMMA_PI_ALLOW_UNSUPPORTED:-0}"

fail() {
  echo "Error: $*" >&2
  exit 1
}

echo "Gemma Pi Local installer"
echo "Project: ${ROOT_DIR}"

if [[ "$(uname -s)" != "Linux" && "${ALLOW_UNSUPPORTED}" != "1" ]]; then
  fail "V0 supports Linux only. Set GEMMA_PI_ALLOW_UNSUPPORTED=1 for development."
fi

ARCH="$(uname -m)"
if [[ "${ARCH}" != "aarch64" && "${ARCH}" != "arm64" && "${ALLOW_UNSUPPORTED}" != "1" ]]; then
  fail "V0 requires ARM64; detected ${ARCH}."
fi

if [[ -r /proc/meminfo && "${ALLOW_UNSUPPORTED}" != "1" ]]; then
  MEM_TOTAL_KB="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
  if [[ -n "${MEM_TOTAL_KB}" && "${MEM_TOTAL_KB}" -lt 7000000 ]]; then
    fail "V0 requires an 8 GB Raspberry Pi; less than 7,000,000 kB was detected."
  fi
fi

AVAILABLE_KB="$(df -Pk "${ROOT_DIR}" | awk 'NR == 2 {print $4}')"
if [[ -n "${AVAILABLE_KB}" && "${AVAILABLE_KB}" -lt 8388608 ]]; then
  fail "At least 8 GB of free disk is required for runtime and model import."
fi

command -v python3 >/dev/null 2>&1 || fail "python3 is required."

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Creating Python environment..."
  if ! python3 -m venv "${VENV_DIR}"; then
    fail "Could not create a venv. On Debian, install python3-venv and retry."
  fi
fi

echo "Installing pinned Pi runtime and web dependencies..."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/requirements-pi.txt"

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

echo
echo "Installation complete."
echo "Start with: ${HOME}/.local/bin/gemma-pi start"
echo "Then open:  http://<raspberry-pi-ip>:8080"
if [[ ":${PATH}:" != *":${HOME}/.local/bin:"* ]]; then
  echo "Tip: add ${HOME}/.local/bin to PATH to run 'gemma-pi' directly."
fi
