# Fastdown CLI 参考

可执行文件名：`fast-download`。单个静态二进制，内含 API 客户端、本地下载器与 MCP stdio 服务端。

---

## 安装

```bash
curl -fsSL https://fastdown.pro/cli | sh -s -- --agent auto
```

安装脚本做的事：

1. 识别操作系统（macOS / Linux / Windows）与架构；
2. 从 `https://fastdown.pro/cli/<version>/` 拉取对应归档（`.tar.gz`，Windows 为 `.zip`）；
3. 安装到 `~/.local/bin`（Windows 为用户目录下的 `fast-download` 目录），已在 `PATH` 时直接可用；
4. `--agent auto` 会在安装后调用 `setup agent --auto`，把 MCP 配置写进检测到的 Agent。

可选环境变量：

| 变量 | 作用 |
|---|---|
| `FAST_DOWNLOAD_VERSION` | 固定版本，例如 `0.6.0`，默认 `latest` |
| `FAST_DOWNLOAD_INSTALL_DIR` | 指定安装目录 |
| `FAST_DOWNLOAD_INSTALL_URL` | 镜像安装脚本的上游地址 |

验证：

```bash
fast-download --version
fast-download --help
```

---

## 登录

```bash
fast-download auth login                 # 打开系统浏览器完成 Google 登录
fast-download auth login --key <key>     # 直接用 connect key / API Key
fast-download auth status                # 人读格式
fast-download auth status --json         # 账号、套餐、配额
fast-download auth logout                # 服务端吊销会话并清除本地配置
```

登录流程刻意不让 Agent 接触密码：CLI 打开系统浏览器，用户在浏览器里完成 Google 登录，CLI 轮询结果后把会话写进本地配置（`0600`）。

会话默认不过期，直到 `logout` 或在服务端吊销。

---

## 解析

```bash
fast-download parse "<链接或分享口令>" [--json] [--media-type video|audio|image]
```

不带 `--json` 时输出人类可读的三段：标题、每类媒体的 URL、配额余量。带 `--json` 时输出：

```json
{ "ok": true, "data": { "platform": "tiktok", "title": "...", "media": [ ... ], "quota": { ... } } }
```

`parse` 只解析不落盘，适合「先看看有没有」「把直链交给别的工具」。

---

## 下载

```bash
fast-download download "<链接或分享口令>" \
  --output ./downloads \
  --name "自定义文件名" \
  --media-type video|audio|image \
  --json
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--output` | `./downloads` | 输出目录，不存在会自动创建 |
| `--name` | 解析出的标题 | 文件名基名，扩展名按媒体类型补 |
| `--media-type` | 自适应 | `audio` 取音轨，`image` 取图文笔记的全部图片 |

`download` 是「解析一次 + 下载选中的媒体」，所以只扣一次配额。`--json` 输出：

```json
{ "ok": true, "data": { "...": "解析结果" }, "files": [ { "path": "/abs/path/file.mp4", "bytes": 1234567 } ] }
```

### 警告走 stderr

当最优选择有取舍时，警告写到 **stderr**，stdout 保持干净（方便 `| jq`）：

```
warning: progressive_video_only_360p — higher resolutions are video-only streams; saved the highest resolution that still has audio
```

`--json` 时同一批警告在 `data.warnings` 里。已知码：`video_has_no_audio`、`progressive_video_only_360p`、`no_media_after_selection`；未知码原样打印。

---

## 配额与订阅

```bash
fast-download quota              # 人类可读
fast-download quota --json
fast-download billing upgrade --plan pro|max [--open=false]
fast-download billing portal [--open=false]
```

`billing upgrade` 会创建 Stripe Checkout 并在浏览器打开；`--open=false` 只打印 URL（适合远程服务器）。订阅状态以 Stripe webhook 为准，CLI 不会「乐观」地认为升级成功 —— 用 `quota --json` 确认 `plan_id` 变了才算生效。

---

## 接入 Agent（MCP）

```bash
fast-download setup agent                # 打印 mcpServers 配置片段
fast-download setup agent --print        # 同上，语义更明确
fast-download setup agent --auto         # 写入所有检测到的 Agent
fast-download setup agent --auto --json  # 机器可读的执行报告
fast-download mcp --stdio                # 手动以 stdio 方式启动 MCP 服务端
```

写入行为：**追加式**，保留已有 server 与无关键；已存在 `fast-download` 条目时不动它。命令写入的是二进制的**绝对路径**，所以从 Dock / 启动台拉起的 GUI Agent 不依赖 shell 的 `PATH`。

支持的目标：

| Agent | 配置文件 |
|---|---|
| Codex | `~/.codex/config.toml` + `~/.codex/skills/fast-download/SKILL.md` |
| Claude Code | `claude mcp add -s user`，失败时回退 `~/.claude.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `<user-data>/Code/User/mcp.json` |
| OpenCode | `~/.config/opencode/opencode.json` |
| Gemini CLI | `~/.gemini/settings.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

改完重启 Agent 应用。MCP 工具说明见 [`mcp.md`](mcp.md)。

---

## 全局参数与环境变量

| 参数 | 说明 |
|---|---|
| `--json` | 机器可读输出 |
| `--base-url` | 覆盖 API 地址（默认 `https://fastdown.pro/api`） |
| `--session-token` | 覆盖会话 token，优先用 `auth login` |
| `--timeout` | 单请求超时（Go duration，如 `20s`） |
| `--max-retries` | 瞬时错误重试次数，默认 2 |
| `--profile` | 使用配置文件里的指定 profile |
| `--config` | 覆盖配置文件路径 |

| 环境变量 | 说明 |
|---|---|
| `FAST_DOWNLOAD_SESSION_TOKEN` | 会话 token（CI 里常用） |
| `FAST_DOWNLOAD_BASE_URL` | API 地址 |
| `FAST_DOWNLOAD_KEY` | 安装脚本读取的连接 key |

优先级：命令行参数 > 环境变量 > 配置文件 > 默认值。

配置文件：`~/.config/fast-download/config.toml`（Windows 为 `%USERPROFILE%\.config\fast-download\`），权限 `0600`。

---

## 退出码

| 退出码 | 含义 |
|---:|---|
| `0` | 成功 |
| `1` | 一般错误（网络、内部错误、下载失败） |
| `3` | 链接层面不可用：`NO_MEDIA`、`PARSE_FAILED`、`UNSUPPORTED_URL`、`NOT_FOUND` |
| `5` | 需要处理账号：`AUTH_REQUIRED`、`QUOTA_EXCEEDED`，以及 HTTP 401/403/429 |

脚本里判断「要不要重试」用退出码 `5` 与 `3` 区分：`5` 去登录或充值，`3` 换链接，`1` 才考虑重试。

---

## 排查

| 现象 | 处理 |
|---|---|
| `AUTH_REQUIRED` | `fast-download auth login`，或 `auth login --key <key>` |
| `QUOTA_EXCEEDED` | `fast-download quota` 看余量与重置时间；`billing upgrade --plan pro` |
| `UNSUPPORTED_URL` | 链接不在支持列表，见 README「支持平台」 |
| `NOT_FOUND` | 内容私密、已删或需要登录；换公开链接 |
| Agent 里看不到工具 | 重启 Agent 应用；`fast-download setup agent --auto --json` 看是否写入成功 |
| 从 GUI 启动的 Agent 报找不到命令 | 用 `setup agent` 重写配置，它会写绝对路径 |
