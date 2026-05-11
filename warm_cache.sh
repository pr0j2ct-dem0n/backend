#!/bin/bash
# Warm cache script - safe defaults for Intel i3-6100 (2 cores / 4 threads)
# Run from project root. Logs appended to warm_cache.log

BASE_URL=${BASE_URL:-http://127.0.0.1:8000}
LOG_FILE=${LOG_FILE:-/home/test/coding/backend/warm_cache.log}

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

echo "$(timestamp) warm start" >> "$LOG_FILE"

# Use short per-request timeout to avoid hanging many seconds
curl_opts=(--silent --show-error --fail --max-time 10)

endpoints=(
  "/sewer-pipe/gu"
  "/api/dashboard/all"
)

for ep in "${endpoints[@]}"; do
  url="$BASE_URL$ep"
  if curl "${curl_opts[@]}" "$url" >/dev/null 2>>"$LOG_FILE"; then
    echo "$(timestamp) OK $ep" >> "$LOG_FILE"
  else
    echo "$(timestamp) FAIL $ep" >> "$LOG_FILE"
  fi
  # small delay to avoid burst
  sleep 1
done

echo "$(timestamp) warm end" >> "$LOG_FILE"
