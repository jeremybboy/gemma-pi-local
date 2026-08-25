#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
MODEL_ID="${GEMMA_PI_MODEL:-gemma4-e4b}"
FAILURES=0
SYSTEM="$(uname -s)"

check() {
  local label="$1"
  local value="$2"
  local status="$3"
  printf '%-22s %s\n' "${label}" "${value}"
  [[ "${status}" == "ok" ]] || FAILURES=$((FAILURES + 1))
}

echo "Gemma Pi Local doctor"
echo

if [[ "${SYSTEM}" == "Linux" || "${SYSTEM}" == "Darwin" ]]; then
  check "Operating system" "${SYSTEM} [ok]" ok
else
  check "Operating system" "${SYSTEM} [unsupported]" fail
fi

ARCH="$(uname -m)"
if [[ "${ARCH}" == "aarch64" || "${ARCH}" == "arm64" ]]; then
  check "Architecture" "${ARCH} [ok]" ok
else
  check "Architecture" "${ARCH} [V0 expects ARM64]" fail
fi

if [[ "${SYSTEM}" == "Linux" && -r /proc/meminfo ]]; then
  MEM_TOTAL_KB="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
  MEM_AVAILABLE_KB="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  check "Memory" "$((MEM_TOTAL_KB / 1024)) MiB total, $((MEM_AVAILABLE_KB / 1024)) MiB available" "$([[ "${MEM_TOTAL_KB}" -ge 7000000 ]] && echo ok || echo fail)"
elif [[ "${SYSTEM}" == "Darwin" ]]; then
  MEM_TOTAL_BYTES="$(sysctl -n hw.memsize 2>/dev/null || true)"
  if [[ "${MEM_TOTAL_BYTES}" =~ ^[0-9]+$ ]]; then
    check "Memory" "$((MEM_TOTAL_BYTES / 1024 / 1024)) MiB total [ok]" "$([[ "${MEM_TOTAL_BYTES}" -ge 7516192768 ]] && echo ok || echo fail)"
  else
    check "Memory" "unavailable" fail
  fi
else
  check "Memory" "unavailable" fail
fi

DISK_AVAILABLE_KB="$(df -Pk "${ROOT_DIR}" | awk 'NR == 2 {print $4}')"
check "Disk free" "$((DISK_AVAILABLE_KB / 1024 / 1024)) GiB" "$([[ "${DISK_AVAILABLE_KB}" -ge 4194304 ]] && echo ok || echo fail)"

if [[ -x "${VENV_DIR}/bin/python" ]]; then
  check "Python" "$("${VENV_DIR}/bin/python" --version 2>&1) [ok]" ok
else
  check "Python environment" "missing; run the installer for this platform" fail
fi

if [[ -x "${VENV_DIR}/bin/litert-lm" ]]; then
  check "LiteRT-LM" "$("${VENV_DIR}/bin/litert-lm" --version 2>&1)" ok
  if "${VENV_DIR}/bin/litert-lm" list 2>/dev/null | awk -v model="${MODEL_ID}" '$1 == model {found=1} END {exit !found}'; then
    check "Model ${MODEL_ID}" "imported [ok]" ok
  else
    check "Model ${MODEL_ID}" "not imported" fail
  fi
else
  check "LiteRT-LM" "missing; run the installer for this platform" fail
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  check "Container tools" "Docker CLI + Compose [ok]" ok
elif [[ "${GEMMA_PI_SEARCH_ENABLED:-true}" =~ ^(0|false|no|off)$ ]]; then
  check "Container tools" "unavailable; web search disabled [ok]" ok
else
  check "Container tools" "missing; web search cannot start" fail
fi

if [[ "${SYSTEM}" == "Darwin" ]]; then
  if command -v colima >/dev/null 2>&1; then
    check "Container VM" "Colima available [ok]" ok
  else
    check "Container VM" "Colima missing; install with Homebrew" fail
  fi
  check "Temperature" "unavailable through standard macOS APIs [info]" ok
  check "Firmware throttle" "not applicable on macOS [info]" ok
elif command -v vcgencmd >/dev/null 2>&1; then
  check "Temperature" "$(vcgencmd measure_temp 2>/dev/null)" ok
  THROTTLED="$(vcgencmd get_throttled 2>/dev/null)"
  check "Firmware throttle" "${THROTTLED}" "$([[ "${THROTTLED}" == "throttled=0x0" ]] && echo ok || echo fail)"
else
  check "vcgencmd" "unavailable (expected outside Raspberry Pi OS)" fail
fi

echo
if [[ "${FAILURES}" -eq 0 ]]; then
  echo "Doctor result: ready"
  exit 0
fi
echo "Doctor result: ${FAILURES} check(s) need attention"
exit 1
