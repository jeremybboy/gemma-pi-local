#!/usr/bin/env bash
set -euo pipefail

APP_URL="${GEMMA_PI_APP_URL:-http://127.0.0.1:8080}"
MODEL_ID="${GEMMA_PI_MODEL:-gemma4-e4b}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "Checking ${APP_URL}/api/status..."
curl -fsS "${APP_URL}/api/status" >"${TMP_DIR}/status.json"
python3 -m json.tool "${TMP_DIR}/status.json" >/dev/null

echo "Sending a small streamed text prompt..."
curl -fsS -N \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${MODEL_ID}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: gemma-pi-ok\"}],\"max_tokens\":32}" \
  "${APP_URL}/api/chat" >"${TMP_DIR}/chat.sse"

grep -q 'data:' "${TMP_DIR}/chat.sse"
grep -q '\[DONE\]' "${TMP_DIR}/chat.sse"
echo "Model response stream:"
sed -n '1,20p' "${TMP_DIR}/chat.sse"
echo "Smoke test passed."
