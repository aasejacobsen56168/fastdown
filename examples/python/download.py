#!/usr/bin/env python3
"""Parse one link, then download the best media entry to disk.

    export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
    python3 examples/python/download.py "https://v.douyin.com/xxxx/" -o ./downloads

Python 3.8+, standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("FASTDOWN_API_BASE", "https://fastdown.pro/api")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
CHUNK = 1024 * 256


def request_json(url: str, key: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"ok": False, "error": {"code": "HTTP_ERROR", "message": raw}}
    except urllib.error.URLError as exc:
        raise SystemExit(f"network error: {exc.reason}") from exc


def safe_name(title: str) -> str:
    cleaned = re.sub(r'[\x00-\x1f/\\:*?"<>|]', "", title or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()[:80]
    return cleaned or "fastdown-media"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a public video with Fastdown")
    parser.add_argument("url", help="share URL or share text")
    parser.add_argument("-o", "--output", default="./downloads", help="output directory")
    parser.add_argument("--type", dest="media_type", choices=["video", "audio", "image"], help="preferred media type")
    args = parser.parse_args()

    key = os.environ.get("FASTDOWN_API_KEY")
    if not key:
        raise SystemExit("set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)")

    prefer = {"watermark": False}
    if args.media_type:
        prefer["media_type"] = args.media_type

    status, body = request_json(f"{API}/v1/parse", key, {"url": args.url, "prefer": prefer})
    if not body.get("ok"):
        err = body.get("error") or {}
        print(f"parse failed: {err.get('code')} — {err.get('message')}", file=sys.stderr)
        print(f"request_id: {body.get('request_id')}", file=sys.stderr)
        raise SystemExit(5 if status in (401, 403, 429) else 3)

    data = body["data"]
    media = (data.get("media") or [{}])[0]
    if not media.get("url"):
        raise SystemExit("no downloadable media in the response")

    out_dir = Path(args.output).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{safe_name(data.get('title'))}.{media.get('ext') or 'mp4'}"

    print(f"downloading: {data.get('title')} ({data.get('platform')})")

    req = urllib.request.Request(media["url"], headers={"user-agent": UA})
    written = 0
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                written += len(chunk)
    except urllib.error.URLError as exc:
        raise SystemExit(f"download failed: {exc.reason}") from exc

    quota = data.get("quota") or {}
    print(f"saved: {dest.resolve()} ({written} bytes)")
    print(f"quota: {quota.get('remaining')}/{quota.get('daily_limit')} remaining")


if __name__ == "__main__":
    main()
