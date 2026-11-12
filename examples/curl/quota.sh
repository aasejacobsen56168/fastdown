#!/usr/bin/env sh
# Show the current plan and today's parse quota.
#
#   export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
#   sh examples/curl/quota.sh
#
# Requires: curl, jq.

set -eu

: "${FASTDOWN_API_KEY:?set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)}"
API="${FASTDOWN_API_BASE:-https://fastdown.pro/api}"

RESP=$(curl -sS "$API/v1/quota" -H "Authorization: Bearer $FASTDOWN_API_KEY")

if [ "$(printf '%s' "$RESP" | jq -r '.ok')" != "true" ]; then
  printf 'quota failed: %s (request_id %s)\n' \
    "$(printf '%s' "$RESP" | jq -r '.error.code')" \
    "$(printf '%s' "$RESP" | jq -r '.request_id')" >&2
  exit 5
fi

printf '%s' "$RESP" |
  jq -r '.data.quota | "plan=\(.plan_id) used=\(.used)/\(.daily_limit) remaining=\(.remaining) reset_at=\(.reset_at)"'
