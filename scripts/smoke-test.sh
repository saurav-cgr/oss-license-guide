#!/usr/bin/env bash
#
# Deployment smoke test for the portable MVP release.
#
# Verifies that a clean Docker Compose launch serves the frontend, routes /api
# through the reverse proxy, exposes only the web endpoint publicly, performs a
# complete deterministic analysis, and contains no secrets in responses.
#
# Usage: scripts/smoke-test.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WEB_URL="http://localhost:8080"
COMPOSE="docker compose"

log() { printf '\n==> %s\n' "$*"; }

cleanup() {
  log "Tearing down the stack"
  $COMPOSE down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "Building images"
$COMPOSE build --quiet

log "Starting the stack"
$COMPOSE up -d

log "Waiting for the web container to become healthy"
for _ in $(seq 1 60); do
  if [ "$($COMPOSE ps --format '{{.Service}} {{.Health}}' | awk '$1=="web" {print $2}')" = "healthy" ]; then
    break
  fi
  sleep 2
done
if [ "$($COMPOSE ps --format '{{.Service}} {{.Health}}' | awk '$1=="web" {print $2}')" != "healthy" ]; then
  echo "ERROR: web container did not become healthy" >&2
  exit 1
fi

log "Checking the frontend is delivered"
if ! curl -fsS "$WEB_URL/" | grep -q "Open Source License Information Assistant"; then
  echo "ERROR: frontend index was not served" >&2
  exit 1
fi

log "Checking /api is routed through the reverse proxy"
HEALTH="$(curl -fsS "$WEB_URL/api/v1/health")"
if ! echo "$HEALTH" | grep -q '"status":"ok"'; then
  echo "ERROR: health via the proxy failed: $HEALTH" >&2
  exit 1
fi

log "Checking the providers endpoint through the proxy"
if ! curl -fsS "$WEB_URL/api/v1/providers" | grep -q '"gemini"'; then
  echo "ERROR: providers endpoint failed via the proxy" >&2
  exit 1
fi

log "Running one complete deterministic analysis through the proxy"
ANALYSIS="$(curl -fsS -X POST "$WEB_URL/api/v1/analyses" \
  -H 'Content-Type: application/json' \
  -d '{"expression":"MIT","facts":{"action":"use","distribution":false}}')"
if ! echo "$ANALYSIS" | grep -q '"outcome"'; then
  echo "ERROR: analysis did not return an outcome" >&2
  exit 1
fi

log "Confirming no API key material or secrets appear in responses"
if echo "$ANALYSIS$HEALTH" | grep -qEi 'sk-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z]{20}|X-Model-Key|Bearer '; then
  echo "ERROR: possible secret leak detected in responses" >&2
  exit 1
fi

log "Confirming only the web endpoint is published to the host"
PUBLISHED="$(docker ps --format '{{.Ports}}' | grep -c '8080->' || true)"
API_PUBLISHED="$(docker ps --format '{{.Ports}}' | grep -c '8000->' || true)"
if [ "$PUBLISHED" -lt 1 ] || [ "$API_PUBLISHED" -ne 0 ]; then
  echo "ERROR: expected only the web port published; api published count=$API_PUBLISHED" >&2
  exit 1
fi

echo
echo "Smoke test passed: frontend delivered, /api proxied, analysis works, no secrets, only web exposed."
