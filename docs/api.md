# Fastdown API 参考

Base URL：`https://fastdown.pro/api`

所有响应都是 JSON，统一信封：

```json
{ "ok": true,  "request_id": "req_...", "data": { } }
{ "ok": false, "request_id": "req_...", "error": { "code": "...", "message": "...", "retryable": false } }
```

`request_id` 每次请求都不同。**开 issue 排查时请带上它** —— 服务端日志按这个 ID 检索。

机器可读的定义：<https://fastdown.pro/openapi.json>（本仓库也存了 [`openapi.json`](../openapi.json)）。

---

## 鉴权

```http
Authorization: Bearer <token>
```

两种 token 等价，指向同一个用户、同一份配额与账单：

| 前缀 | 来源 | 用途 | 有效期 |
|---|---|---|---|
| `fd_sess_` | Google 登录 / 邮箱验证码（网页或 `fast-download auth login`） | 人使用、CLI | 直到登出，服务端可吊销 |
| `fd_live_` | <https://fastdown.pro/integrations> 创建 | 服务端、CI、常驻 Agent | 直到轮换或吊销 |

API Key 规则：

- 每个账号最多 **3 个活跃 Key**，超出返回 `400 KEY_LIMIT_REACHED`；
- 明文只在创建 / 轮换时返回一次，服务端只存 `sha256` 与前 12 位 `prefix`；
- **Key 不能管理 Key**：`/v1/keys*` 只接受会话 token，否则 `403 SESSION_REQUIRED`；
- 轮换会把旧 Key 立刻标记为吊销，新 Key 继承同一个名字；
- `last_used_at` 最多每分钟写一次，避免高频调用打爆数据库。

`GET /v1/health` 不需要鉴权。

---

## POST /v1/parse

解析一条公开分享链接。

```bash
curl -sS https://fastdown.pro/api/v1/parse \
  -H "Authorization: Bearer $FASTDOWN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://v.douyin.com/xxxx/"}'
```

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `url` | string | 是 | 分享链接，或包含链接的整段分享口令。服务端会自己抽取 URL |
| `prefer.watermark` | boolean | 否 | `true` 时优先有水印版本（平台提供时）；默认 `false`，优选无水印 |
| `prefer.media_type` | string | 否 | `video` / `audio` / `image`，默认按内容自适应 |

### 响应

```json
{
  "ok": true,
  "request_id": "req_53069806a84e473a8e83e5fea129f6e1",
  "data": {
    "platform": "tiktok",
    "title": "Shin godzilla #movie",
    "author": "yeuphimzz",
    "media": [
      {
        "type": "video",
        "url": "https://...",
        "watermark": false,
        "quality": "hd_no_watermark",
        "ext": "mp4"
      }
    ],
    "cover_url": "https://...",
    "duration": 88,
    "parse_time": "2026-11-11T02:20:29.604Z",
    "warnings": [],
    "quota": { "plan_id": "free", "daily_limit": 50, "used": 3, "remaining": 47, "reset_at": "2026-11-13T00:00:00.000Z" },
    "elapsed_ms": 1299
  }
}
```

`media` 是**候选列表，按推荐顺序排列**，`media[0]` 即最优选择：

- 视频：优先「已带音轨」的混流，避免下到无声版；同类型可能有多个候选，按画质与是否带水印排序；
- 音频：请求 `prefer.media_type=audio`、或内容本身没有视频轨时附带一条；
- 图片：图文笔记返回全部图片（受数量上限约束），`type` 为 `image`。

`quality`、`ext` 是**可选字段**：服务端在不同上游能力下可能省略。客户端应按 `type` 判断用途，`ext` 缺省时按 `mp4` 处理，不要假设字段一定存在。

### 媒体选择规则

| 情况 | 行为 |
|---|---|
| 平台同时有无水印版与带水印版 | 默认给无水印；`prefer.watermark=true` 时优先带水印版 |
| 高分版本是纯视频轨（无音轨） | 退到「最高分辨率且带音轨」的混流，并给 `progressive_video_only_360p` 警告 |
| 只有一条无音轨视频 | 照常返回，附 `video_has_no_audio` 警告 |
| 选不到任何媒体 | 422 `NO_MEDIA`，不扣配额 |

### 警告码

| code | 含义 | 建议 |
|---|---|---|
| `video_has_no_audio` | 唯一可用的视频轨没有音轨 | 需要声音就另取 `audio` 轨自行合成 |
| `progressive_video_only_360p` | 混流上限 360p，更高分辨率只能拿纯视频 | 接受 360p，或取高码率视频轨 + 音频轨 |
| `no_media_after_selection` | 应用 `prefer` 后没有可用条目 | 去掉 `prefer` 重试一次 |

未知警告码请原样透传，不要据此报错 —— 新增警告是向后兼容的。

### 配额语义

- **只有成功返回可用媒体时才扣 1 次**；
- 上游超时、限流、链接失效、无媒体，都不扣；
- 余量为 0 时直接 `429 QUOTA_EXCEEDED`，不会打到上游。

### 错误码

| HTTP | code | retryable | 含义 |
|---:|---|---|---|
| 400 | `BAD_JSON` | false | 请求体不是合法 JSON |
| 400 | `INVALID_INPUT` | false | `url` 缺失或不是可用链接 |
| 401 | `AUTH_REQUIRED` | false | 没带 token 或 token 已失效 |
| 403 | `SESSION_REQUIRED` | false | 该接口只接受登录会话，不接受 API Key |
| 422 | `UNSUPPORTED_URL` | false | 平台不支持 |
| 422 | `NOT_FOUND` | false | 帖子私密、已删除、需登录或年龄验证 |
| 422 | `NO_MEDIA` | false | 解析成功但没有可下载媒体 |
| 429 | `QUOTA_EXCEEDED` | false | 今日配额用完，`retry_after` 给出重置秒数 |
| 500 | `INTERNAL_ERROR` | false | 服务端异常 |
| 502 | `UPSTREAM_AUTH` / `UPSTREAM_NETWORK` / `UPSTREAM_PAYLOAD` | true | 上游鉴权 / 网络 / 返回结构异常 |
| 503 | `UPSTREAM_RATE_LIMITED` | true | 上游限流 |
| 504 | `UPSTREAM_TIMEOUT` | true | 上游超时 |

重试建议：只对 `retryable: true` 做指数退避（1s → 2s → 4s，最多 3 次）；`429` 按 `retry_after` 等待。

---

## GET /v1/quota

```json
{ "ok": true, "request_id": "req_...", "data": { "quota": { "plan_id": "free", "daily_limit": 50, "used": 3, "remaining": 47, "reset_at": "2026-11-13T00:00:00.000Z" } } }
```

`reset_at` 是 UTC ISO 时间：配额按 **UTC 自然日**重置，即北京时间每天 08:00。

---

## GET /v1/me

```json
{
  "ok": true,
  "request_id": "req_...",
  "data": {
    "authenticated": true,
    "user": { "id": "usr_...", "email": "you@example.com", "name": "Your Name", "picture_url": "https://..." },
    "plan": { "plan_id": "free", "daily_limit": 50, "used": 0, "remaining": 50, "reset_at": "..." },
    "stripe": { "customer_id": "cus_...", "subscription_id": "sub_...", "subscription_plan": "pro", "status": "active" }
  }
}
```

`stripe` 在从未订阅过的账号上是空对象 `{}`。

---

## API Key 管理

以下接口**只接受会话 token**（`fd_sess_...`），用 API Key 调用会得到 `403 SESSION_REQUIRED` —— 这样泄露的 Key 无法给自己续命。

### `GET /v1/keys`

```json
{ "ok": true, "data": { "keys": [ { "id": "key_...", "name": "CI", "prefix": "fd_live_ab12", "created_at": "...", "last_used_at": "...", "revoked_at": null } ], "limit": 3, "active": 1 } }
```

### `POST /v1/keys`

Body 可选：`{"name":"CI"}`。

```json
{ "ok": true, "data": { "key": { "id": "key_...", "name": "CI", "prefix": "fd_live_ab12", "...": "..." }, "secret": "fd_live_...（只出现这一次）" } }
```

### `POST /v1/keys/{id}/rotate`

吊销旧 Key，返回同名新 Key：

```json
{ "ok": true, "data": { "key": { "...": "..." }, "secret": "fd_live_...", "revoked_id": "key_..." } }
```

### `POST /v1/keys/{id}/revoke`

```json
{ "ok": true, "data": { "revoked": true, "id": "key_..." } }
```

| HTTP | code | 含义 |
|---:|---|---|
| 400 | `KEY_LIMIT_REACHED` | 已有 3 个活跃 Key |
| 403 | `SESSION_REQUIRED` | 用 Key 管理 Key |
| 404 | `KEY_NOT_FOUND` | Key 不存在或已吊销 |

---

## 计费

### `POST /v1/billing/checkout`

Body：`{"plan_id":"pro","success_url":"https://...","cancel_url":"https://..."}`（后两个可选）。

```json
{ "ok": true, "data": { "checkout_url": "https://checkout.stripe.com/...", "session_id": "cs_..." } }
```

跳转到 `checkout_url` 完成支付。订阅状态只在 Stripe webhook 确认后生效 —— 服务端不相信前端回调。

### `POST /v1/billing/portal`

```json
{ "ok": true, "data": { "portal_url": "https://billing.stripe.com/..." } }
```

用于改卡、看发票、取消订阅。

### 套餐

| plan_id | 月费 | 每日成功解析 |
|---|---:|---:|
| `free` | $0 | 50 |
| `pro` | $5 | 1,000 |
| `max` | $10 | 3,000 |

---

## 健康检查

`GET /v1/health`，无需鉴权：

```json
{ "ok": true, "request_id": "req_...", "data": { "service": "fast-download-api", "ok": true, "time": "2026-11-12T13:13:32.072Z" } }
```

---

## 兼容性约定

- 只做**新增式**变更：新字段、新警告码、新错误码都是向后兼容的，客户端应忽略未知字段；
- 字段类型不会变（包括错误里的 `retry_after`、`attempts_left` 等全部是字符串）；
- 破坏性变更会换路径前缀（`/v1` → `/v2`），旧版本至少保留 90 天；
- 解析是同步接口，正常 1–3 秒，超时上限 30 秒；不要用它做批量长任务，批量请控制并发并自行重试。

---

## 示例代码

| 语言 | 文件 |
|---|---|
| curl | [`examples/curl/parse.sh`](../examples/curl/parse.sh) · [`download.sh`](../examples/curl/download.sh) |
| Node 18+ | [`examples/node/parse.mjs`](../examples/node/parse.mjs) · [`download.mjs`](../examples/node/download.mjs) |
| Python 3（仅标准库） | [`examples/python/parse.py`](../examples/python/parse.py) · [`download.py`](../examples/python/download.py) |
| Go | [`examples/go/main.go`](../examples/go/main.go) |
