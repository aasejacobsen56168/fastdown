#!/usr/bin/env sh
# Parse one public share link and print the JSON response.
#
#   export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
#   sh examples/curl/parse.sh "https://v.douyin.com/xxxx/"
#
# Requires: curl, jq. Get a key at https://fastdown.pro/integrations

set -eu

: "${FASTDOWN_API_KEY:?set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)}"
INPUT="${1:?usage: parse.sh <share url or share text>}"
API="${FASTDOWN_API_BASE:-https://fastdown.pro/api}"

BODY=$(jq -n --arg url "$INPUT" '{url: $url, prefer: {watermark: false}}')

RESP=$(curl -sS -X POST "$API/v1/parse" \
  -H "Authorization: Bearer $FASTDOWN_API_KEY" \
  -H "Content-Type: application/json" \
  --data "$BODY")

printf '%s\n' "$RESP" | jq .

if [ "$(printf '%s' "$RESP" | jq -r '.ok')" != "true" ]; then
  case "$(printf '%s' "$RESP" | jq -r '.error.code')" in
    AUTH_REQUIRED|QUOTA_EXCEEDED) exit 5 ;;
    NO_MEDIA|PARSE_FAILED|UNSUPPORTED_URL|NOT_FOUND) exit 3 ;;
    *) exit 1 ;;
  esac
fi
