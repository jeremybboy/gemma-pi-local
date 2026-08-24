#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="$ROOT_DIR/deploy/searxng"
ENV_FILE="$STACK_DIR/.env"
LOCAL_URL="http://127.0.0.1:8888"

usage() {
  echo "Usage: $0 {start|stop|status|logs|test}"
}

require_runtime() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed." >&2
    echo "Follow the official Docker Engine instructions for Debian before continuing." >&2
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is not available." >&2
    exit 1
  fi
}

ensure_secret() {
  if [[ -f "$ENV_FILE" ]]; then
    return
  fi
  umask 077
  local secret
  secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  printf 'SEARXNG_SECRET=%s\n' "$secret" >"$ENV_FILE"
  echo "Created a private SearXNG secret in $ENV_FILE"
}

compose() {
  docker compose --project-directory "$STACK_DIR" --env-file "$ENV_FILE" "$@"
}

command_name="${1:-}"
case "$command_name" in
  start)
    require_runtime
    ensure_secret
    compose up -d
    echo "SearXNG is starting on loopback only: $LOCAL_URL"
    ;;
  stop)
    require_runtime
    [[ -f "$ENV_FILE" ]] || { echo "SearXNG has not been configured."; exit 0; }
    compose down
    ;;
  status)
    require_runtime
    [[ -f "$ENV_FILE" ]] || { echo "SearXNG has not been configured."; exit 1; }
    compose ps
    curl --fail --silent --show-error --max-time 5 "$LOCAL_URL/" >/dev/null
    echo "SearXNG HTTP check: ready"
    ;;
  logs)
    require_runtime
    [[ -f "$ENV_FILE" ]] || { echo "SearXNG has not been configured."; exit 1; }
    compose logs --tail=120 searxng
    ;;
  test)
    curl --fail --silent --show-error --max-time 30 \
      --get "$LOCAL_URL/search" \
      --data-urlencode "q=Raspberry Pi" \
      --data "format=json" \
      --data "categories=general"
    echo
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
