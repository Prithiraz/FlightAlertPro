#!/usr/bin/env bash
# scripts/security_smoke.sh
# Security-focused smoke tests for FlightAlertPro.
#
# Usage:
#   SMOKE_BASE_URL=https://api.example.com bash scripts/security_smoke.sh
#
# Optional env vars:
#   ADMIN_TOKEN  – valid JWT for an admin user  (tests that require admin)
#   USER_TOKEN   – valid JWT for a normal user  (tests that require auth)
#
# Requires: curl

set -euo pipefail

BASE_URL="${SMOKE_BASE_URL:-http://localhost:8000}"
PASS=0
FAIL=0

# ── helpers ──────────────────────────────────────────────────────────────────

check() {
  local desc="$1"
  local url="$2"
  local method="${3:-GET}"
  local body="${4:-}"
  local expected_status="${5:-200}"
  local extra_args="${6:-}"

  if [ "$method" = "POST" ] && [ -n "$body" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 \
      -X POST -H "Content-Type: application/json" -d "$body" \
      $extra_args "$url")
  else
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 \
      -X "$method" $extra_args "$url")
  fi

  if [ "$status" = "$expected_status" ]; then
    echo "  PASS  [$expected_status] $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  [$expected_status expected, got $status] $desc"
    FAIL=$((FAIL + 1))
  fi
}

auth_header() {
  local token="$1"
  echo "-H \"Authorization: Bearer $token\""
}

echo "=== Security smoke tests against: $BASE_URL ==="
echo ""

# ── Phase 1: Unauthenticated requests must return 401 ────────────────────────
echo "-- Phase 1: Auth enforcement --"

check "GET /api/alerts/list requires auth (401)"   "$BASE_URL/api/alerts/list"   GET  ""  401
check "POST /api/alerts/create requires auth (401)" "$BASE_URL/api/alerts/create" POST '{}' 401
check "GET /api/me requires auth (401)"             "$BASE_URL/api/me"            GET  ""  401
check "GET /api/billing/status requires auth (401)" "$BASE_URL/api/billing/status" GET "" 401
check "GET /notifications/history requires auth (401)" "$BASE_URL/api/notifications/history" GET "" 401
check "GET /api/saved-searches requires auth (401)" "$BASE_URL/api/saved-searches" GET "" 401

# ── Phase 1: Admin-only endpoints return 401 without token ───────────────────
echo ""
echo "-- Phase 1: Admin endpoint auth --"

check "GET /api/admin/overview requires auth (401)"       "$BASE_URL/api/admin/overview"        GET "" 401
check "GET /api/audit requires auth (401)"                "$BASE_URL/api/admin/audit"           GET "" 401
check "GET /api/metrics requires auth (401)"              "$BASE_URL/api/metrics"               GET "" 401
check "GET /api/search/circuit-breaker-status (401)"      "$BASE_URL/api/search/circuit-breaker-status" GET "" 401

# ── Phase 1: Admin endpoints return 403 for normal user (if USER_TOKEN set) ──
if [ -n "${USER_TOKEN:-}" ]; then
  echo ""
  echo "-- Phase 1: Admin endpoints return 403 for normal user --"
  check "GET /api/admin/overview returns 403 for user" \
    "$BASE_URL/api/admin/overview" GET "" 403 \
    "-H 'Authorization: Bearer ${USER_TOKEN}'"
  check "GET /api/admin/audit returns 403 for user" \
    "$BASE_URL/api/admin/audit" GET "" 403 \
    "-H 'Authorization: Bearer ${USER_TOKEN}'"
fi

# ── Phase 2: Rate limiting triggers on /api/search ───────────────────────────
echo ""
echo "-- Phase 2: Rate limiting on /api/search --"

SEARCH_BODY='{"segments":[{"from_iata":"LHR","to_iata":"JFK","departure_date":"2026-06-01"}]}'
echo "  (sending 35 rapid search requests to trigger per-IP 429)"
GOT_429=0
for i in $(seq 1 35); do
  s=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    -X POST -H "Content-Type: application/json" -d "$SEARCH_BODY" \
    "$BASE_URL/api/search")
  if [ "$s" = "429" ]; then
    GOT_429=1
    break
  fi
done

if [ "$GOT_429" = "1" ]; then
  echo "  PASS  [429] Rate limiting triggered on /api/search"
  PASS=$((PASS + 1))
else
  echo "  FAIL  [429 expected] Rate limiting did NOT trigger on /api/search after 35 requests"
  FAIL=$((FAIL + 1))
fi

# ── Phase 6: Security headers present ────────────────────────────────────────
echo ""
echo "-- Phase 6: Security headers --"

HEADERS=$(curl -s -D - -o /dev/null --max-time 10 "$BASE_URL/health")

for header in "x-content-type-options" "x-frame-options" "referrer-policy" "content-security-policy"; do
  if echo "$HEADERS" | grep -qi "^$header:"; then
    echo "  PASS  Security header present: $header"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  Security header missing: $header"
    FAIL=$((FAIL + 1))
  fi
done

# ── Phase 2: Audit log written after alert create/delete (requires ADMIN_TOKEN + USER_TOKEN) ──
if [ -n "${ADMIN_TOKEN:-}" ] && [ -n "${USER_TOKEN:-}" ]; then
  echo ""
  echo "-- Phase 2: Audit log after alert create/delete --"

  ALERT_BODY='{"from_iata":"LHR","to_iata":"JFK","max_price":500,"currency":"USD","notification_channels":["email"]}'

  ALERT_RESP=$(curl -s -X POST -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${USER_TOKEN}" \
    -d "$ALERT_BODY" "$BASE_URL/api/alerts/create")

  ALERT_ID=$(echo "$ALERT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('alert_id',''))" 2>/dev/null || echo "")

  if [ -n "$ALERT_ID" ]; then
    echo "  INFO  Created alert id=$ALERT_ID"

    # Delete the alert
    curl -s -X DELETE -H "Authorization: Bearer ${USER_TOKEN}" \
      "$BASE_URL/api/alerts/$ALERT_ID" > /dev/null

    # Check audit log
    AUDIT=$(curl -s -H "Authorization: Bearer ${ADMIN_TOKEN}" \
      "$BASE_URL/api/admin/audit?action=alert.create&limit=5")
    if echo "$AUDIT" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('count',0)>0 else 1)" 2>/dev/null; then
      echo "  PASS  Audit log contains alert.create entry"
      PASS=$((PASS + 1))
    else
      echo "  FAIL  Audit log does not contain alert.create entry"
      FAIL=$((FAIL + 1))
    fi
  else
    echo "  SKIP  Could not create test alert (check USER_TOKEN)"
  fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
