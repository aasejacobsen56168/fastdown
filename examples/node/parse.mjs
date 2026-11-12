#!/usr/bin/env node
// Parse one public share link and print the JSON response.
//
//   export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
//   node examples/node/parse.mjs "https://v.douyin.com/xxxx/"
//
// Node 18+ only, no dependencies.

const API = process.env.FASTDOWN_API_BASE ?? "https://fastdown.pro/api";
const KEY = process.env.FASTDOWN_API_KEY;

function fail(message, code = 1) {
  console.error(message);
  process.exit(code);
}

if (!KEY) fail("set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)", 5);

const input = process.argv[2];
if (!input) fail("usage: node parse.mjs <share url or share text>", 2);

const res = await fetch(`${API}/v1/parse`, {
  method: "POST",
  headers: {
    authorization: `Bearer ${KEY}`,
    "content-type": "application/json",
  },
  body: JSON.stringify({ url: input, prefer: { watermark: false } }),
});

const body = await res.json().catch(() => null);
if (!body) fail(`HTTP ${res.status}: response was not JSON`);

if (!body.ok) {
  const err = body.error ?? {};
  console.error(`parse failed: ${err.code} — ${err.message}`);
  console.error(`request_id: ${body.request_id}  retryable: ${err.retryable}`);
  // 401/403: fix auth. 429: quota. Everything else: probably the link.
  process.exit(res.status === 401 || res.status === 403 || res.status === 429 ? 5 : 3);
}

console.log(JSON.stringify(body, null, 2));
