#!/usr/bin/env bash
# scripts/smoke_test.sh
# Quick post-deploy health check.
# Usage:  SMOKE_BASE_URL=https://api.example.com bash scripts/smoke_test.sh
set -euo pipefail

BASE_URL="${SMOKE_BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0

check() {
  local desc="$1"
  local url="$2"
  local expected_status="${3:-200}"

  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url")
  if [ "$status" = "$expected_status" ]; then
    echo "  PASS  $desc ($url) → HTTP $status"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $desc ($url) → expected HTTP $expected_status, got $status"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Smoke tests against: $BASE_URL ==="

check "/health"                  "$BASE_URL/health"
check "/health/integrations"     "$BASE_URL/health/integrations"
check "/api/metadata/stats"      "$BASE_URL/api/metadata/stats"
check "/api/systemcheck"         "$BASE_URL/api/systemcheck"

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
