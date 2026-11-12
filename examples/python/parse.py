#!/usr/bin/env python3
"""Parse one public share link and print the JSON response.

    export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
    python3 examples/python/parse.py "https://v.douyin.com/xxxx/"

Python 3.8+, standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("FASTDOWN_API_BASE", "https://fastdown.pro/api")


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
        except json.JSONDecodeError:
            return exc.code, {"ok": False, "error": {"code": "HTTP_ERROR", "message": raw}}
    except urllib.error.URLError as exc:
        raise SystemExit(f"network error: {exc.reason}") from exc


def parse(url: str, key: str, media_type: str | None = None) -> dict:
    prefer: dict = {"watermark": False}
    if media_type:
        prefer["media_type"] = media_type
    status, body = request_json(f"{API}/v1/parse", key, {"url": url, "prefer": prefer})
    if not body.get("ok"):
        err = body.get("error") or {}
        print(f"parse failed: {err.get('code')} — {err.get('message')}", file=sys.stderr)
        print(f"request_id: {body.get('request_id')}  retryable: {err.get('retryable')}", file=sys.stderr)
        # 401/403: fix auth. 429: quota. Others: probably the link.
        raise SystemExit(5 if status in (401, 403, 429) else 3)
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a public video share link with Fastdown")
    parser.add_argument("url", help="share URL or share text")
    parser.add_argument("--type", dest="media_type", choices=["video", "audio", "image"], help="preferred media type")
    parser.add_argument("--raw", action="store_true", help="print the whole response envelope")
    args = parser.parse_args()

    key = os.environ.get("FASTDOWN_API_KEY")
    if not key:
        raise SystemExit("set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)")

    body = parse(args.url, key, args.media_type)
    data = body["data"]

    if args.raw:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return

    print(f"{data.get('title')}  ·  {data.get('platform')}  ·  {data.get('author')}")
    print(f"cover: {data.get('cover_url')}")
    for item in data.get("media", []):
        print(f"{item.get('type'):5s} {item.get('ext', ''):4s} {item.get('quality', ''):20s} {item.get('url')}")
    for warning in data.get("warnings", []):
        print(f"warning: {warning}", file=sys.stderr)
    quota = data.get("quota", {})
    print(f"quota: {quota.get('used')}/{quota.get('daily_limit')} used, {quota.get('remaining')} left")


if __name__ == "__main__":
    main()
