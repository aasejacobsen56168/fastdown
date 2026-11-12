#!/usr/bin/env sh
# Parse one link, then download the best media entry into ./downloads.
#
#   export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
#   sh examples/curl/download.sh "https://v.douyin.com/xxxx/" [output-dir]
#
# Requires: curl, jq. Get a key at https://fastdown.pro/integrations

set -eu

: "${FASTDOWN_API_KEY:?set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)}"
INPUT="${1:?usage: download.sh <share url or share text> [output-dir]}"
OUTDIR="${2:-./downloads}"
API="${FASTDOWN_API_BASE:-https://fastdown.pro/api}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

BODY=$(jq -n --arg url "$INPUT" '{url: $url, prefer: {watermark: false}}')

RESP=$(curl -sS -X POST "$API/v1/parse" \
  -H "Authorization: Bearer $FASTDOWN_API_KEY" \
  -H "Content-Type: application/json" \
  --data "$BODY")

if [ "$(printf '%s' "$RESP" | jq -r '.ok')" != "true" ]; then
  CODE=$(printf '%s' "$RESP" | jq -r '.error.code')
  printf 'parse failed: %s — %s (request_id %s)\n' \
    "$CODE" \
    "$(printf '%s' "$RESP" | jq -r '.error.message')" \
    "$(printf '%s' "$RESP" | jq -r '.request_id')" >&2
  case "$CODE" in
    AUTH_REQUIRED|QUOTA_EXCEEDED) exit 5 ;;
    NO_MEDIA|PARSE_FAILED|UNSUPPORTED_URL|NOT_FOUND) exit 3 ;;
    *) exit 1 ;;
  esac
fi

MEDIA_URL=$(printf '%s' "$RESP" | jq -r '.data.media[0].url')
EXT=$(printf '%s' "$RESP" | jq -r '.data.media[0].ext // "mp4"')
TITLE=$(printf '%s' "$RESP" | jq -r '.data.title // "fastdown-media"')

# Keep the file name filesystem-safe and short.
SAFE=$(printf '%s' "$TITLE" | tr -d '\000-\037/\\:*?"<>|' | tr -s ' ' | sed 's/^\(.\{1,80\}\).*/\1/; s/ *$//')
[ -n "$SAFE" ] || SAFE="fastdown-media"

mkdir -p "$OUTDIR"
DEST="$OUTDIR/$SAFE.$EXT"

printf 'downloading: %s\n' "$TITLE"
curl -fL --retry 2 -# -A "$UA" -o "$DEST" "$MEDIA_URL"

BYTES=$(wc -c < "$DEST" | tr -d ' ')
printf 'saved: %s (%s bytes)\n' "$DEST" "$BYTES"
