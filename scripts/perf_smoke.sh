#!/usr/bin/env bash
# scripts/perf_smoke.sh
# Verifies that repeat identical searches return cache_hit=true.
#
# Usage:
#   ./scripts/perf_smoke.sh [API_BASE_URL]
#
# Default API_BASE_URL: http://localhost:8000

set -euo pipefail

API_BASE="${1:-http://localhost:8000}"

PAYLOAD='{
  "segments": [{"from_iata": "JFK", "to_iata": "LHR", "departure_date": "2026-06-01"}],
  "passengers": {"adults": 1},
  "cabin_class": "economy",
  "currency": "USD"
}'

echo "=== FlightAlertPro perf smoke test ==="
echo "API: $API_BASE"
echo ""

# First search – should be a cache miss
echo "[1/2] First search (expect cache_hit=false)..."
RESP1=$(curl -s -X POST "$API_BASE/api/search" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

CACHE_HIT_1=$(echo "$RESP1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cache_hit', 'MISSING'))")
TIME_1=$(echo "$RESP1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('search_time_ms', 'MISSING'))")

echo "  cache_hit : $CACHE_HIT_1"
echo "  search_time_ms: $TIME_1"

if [ "$CACHE_HIT_1" = "True" ] || [ "$CACHE_HIT_1" = "true" ]; then
  echo "  WARN: First request was already cached (cache may not have been cleared)"
fi

# Second search – must be a cache hit
echo ""
echo "[2/2] Second search (expect cache_hit=true)..."
RESP2=$(curl -s -X POST "$API_BASE/api/search" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

CACHE_HIT_2=$(echo "$RESP2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('cache_hit', 'MISSING'))")
TIME_2=$(echo "$RESP2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('search_time_ms', 'MISSING'))")

echo "  cache_hit : $CACHE_HIT_2"
echo "  search_time_ms: $TIME_2"

echo ""

if [ "$CACHE_HIT_2" = "True" ] || [ "$CACHE_HIT_2" = "true" ]; then
  echo "✅ PASS: Second request was served from cache."
else
  echo "❌ FAIL: Expected cache_hit=true on second request, got: $CACHE_HIT_2"
  exit 1
fi

# Show metrics
echo ""
echo "--- /api/metrics ---"
curl -s "$API_BASE/api/metrics" | python3 -m json.tool
