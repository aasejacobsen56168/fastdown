#!/usr/bin/env node
// Parse one link, then stream the best media entry to disk.
//
//   export FASTDOWN_API_KEY="fd_live_xxxxxxxx"
//   node examples/node/download.mjs "https://v.douyin.com/xxxx/" [output-dir] [--type audio|image|video]
//
// Node 18+ only, no dependencies.

import { createWriteStream } from "node:fs";
import { mkdir } from "node:fs/promises";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import path from "node:path";

const API = process.env.FASTDOWN_API_BASE ?? "https://fastdown.pro/api";
const KEY = process.env.FASTDOWN_API_KEY;
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

function fail(message, code = 1) {
  console.error(message);
  process.exit(code);
}

if (!KEY) fail("set FASTDOWN_API_KEY first (create one at https://fastdown.pro/integrations)", 5);

const args = process.argv.slice(2);
const typeIndex = args.indexOf("--type");
const mediaType = typeIndex === -1 ? undefined : args[typeIndex + 1];
if (typeIndex !== -1) args.splice(typeIndex, 2);

const input = args[0];
if (!input) fail("usage: node download.mjs <share url> [output-dir] [--type audio|image|video]", 2);
const outDir = args[1] ?? "./downloads";

async function parse(url) {
  const res = await fetch(`${API}/v1/parse`, {
    method: "POST",
    headers: { authorization: `Bearer ${KEY}`, "content-type": "application/json" },
    body: JSON.stringify({ url, prefer: { watermark: false, media_type: mediaType } }),
  });
  const body = await res.json().catch(() => null);
  if (!body) fail(`HTTP ${res.status}: response was not JSON`);
  if (!body.ok) {
    console.error(`parse failed: ${body.error?.code} — ${body.error?.message}`);
    console.error(`request_id: ${body.request_id}`);
    process.exit(res.status === 401 || res.status === 403 || res.status === 429 ? 5 : 3);
  }
  return body.data;
}

function safeName(title) {
  const cleaned = String(title || "fastdown-media")
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001f/\\:*?"<>|]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
  return cleaned || "fastdown-media";
}

const data = await parse(input);
const media = data.media?.[0];
if (!media?.url) fail("no downloadable media in the response", 3);

const file = path.join(outDir, `${safeName(data.title)}.${media.ext || "mp4"}`);
await mkdir(outDir, { recursive: true });

console.log(`downloading: ${data.title} (${data.platform})`);

const res = await fetch(media.url, { headers: { "user-agent": UA } });
if (!res.ok || !res.body) fail(`download failed: HTTP ${res.status}`, 1);

await pipeline(Readable.fromWeb(res.body), createWriteStream(file));

console.log(`saved: ${path.resolve(file)}`);
console.log(`quota: ${data.quota?.remaining}/${data.quota?.daily_limit} remaining`);
