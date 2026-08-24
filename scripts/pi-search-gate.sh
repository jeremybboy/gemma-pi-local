#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
SEARCH_URL="http://127.0.0.1:8888"
LITERT_URL="${GEMMA_PI_LITERT_URL:-http://127.0.0.1:9379/v1}"

fail() {
  echo "GATE FAIL: $*" >&2
  exit 1
}

[[ -x "$VENV_PYTHON" ]] || fail "Run ./install.sh first."
command -v docker >/dev/null 2>&1 || fail "Docker is not installed. See docs/AGENTIC_SEARCH.md."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is unavailable."

echo "=== START SEARXNG ==="
"$ROOT_DIR/scripts/searxng.sh" start

search_ready=0
for _ in $(seq 1 30); do
  if curl --fail --silent --max-time 2 "$SEARCH_URL/" >/dev/null 2>&1; then
    search_ready=1
    break
  fi
  sleep 2
done
[[ "$search_ready" == "1" ]] || {
  "$ROOT_DIR/scripts/searxng.sh" logs || true
  fail "SearXNG did not become ready within 60 seconds."
}

"$ROOT_DIR/scripts/searxng.sh" status

echo "=== LIVE SEARCH ==="
search_json="$(mktemp)"
trap 'rm -f "$search_json"' EXIT
curl --fail --silent --show-error --max-time 30 \
  --get "$SEARCH_URL/search" \
  --data-urlencode "q=Raspberry Pi" \
  --data "format=json" \
  --data "categories=general" >"$search_json"
"$VENV_PYTHON" - "$search_json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
results = payload.get("results", [])
if not isinstance(results, list) or not results:
    raise SystemExit("GATE FAIL: SearXNG returned no results")
engines = sorted(
    {
        engine
        for result in results
        if isinstance(result, dict)
        for engine in result.get("engines", [])
        if isinstance(engine, str)
    }
)
print(f"results: {len(results)}")
print(f"engines: {', '.join(engines[:10]) or 'not reported'}")
print(f"first title: {results[0].get('title', 'missing')}")
PY

echo "=== START GEMMA PI LOCAL ==="
if ! curl --fail --silent --max-time 3 "$LITERT_URL/models" >/dev/null 2>&1; then
  "$ROOT_DIR/bin/gemma-pi" start
fi

echo "=== LITERT TOOL-CALL PROBE ==="
set +e
"$VENV_PYTHON" "$ROOT_DIR/scripts/probe-tool-call.py" --base-url "$LITERT_URL"
probe_status=$?
set -e

echo "=== RESOURCE SNAPSHOT ==="
docker stats --no-stream gemma-pi-searxng
echo "Observed SearXNG worker log lines:"
docker logs gemma-pi-searxng 2>&1 | grep -E "Spawning worker|Listening at" | tail -n 10 || echo "No worker lines found."
free -h
if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd measure_temp
  vcgencmd get_throttled
fi

[[ "$probe_status" == "0" ]] || fail "LiteRT-LM did not emit a valid structured tool call."
echo "GATE PASS: SearXNG search and structured Gemma tool calling both worked."
