# MCP 接入：让 Agent 直接会下载

`fast-download` 自带一个 MCP stdio 服务端。接上之后，Codex / Claude Code / Cursor / VS Code / OpenCode / Gemini CLI / Windsurf 就能把「把这个链接的视频下下来」变成一个真实动作 —— 而不是打开浏览器假装下载。

---

## 一条命令装好

先在 <https://fastdown.pro/account> 复制你的 connect key，然后：

```bash
curl -fsSL 'https://fastdown.pro/mcp?key=<connect-key>' | sh
```

这条命令会：安装 / 更新 CLI → 保存 key → 把 MCP server 写进**所有检测到的 Agent** → 打印每个 Agent 的写入结果。

也可以手动两步：

```bash
curl -fsSL https://fastdown.pro/cli | sh -s -- --agent auto
fast-download auth login --key <connect-key>
```

**装完重启 Agent 应用**（GUI 应用启动时读一次配置）。之后在 Agent 里直接说：

> 帮我把这个链接的视频下下来：https://v.douyin.com/xxxx/

---

## 工具

MCP 服务端（`fast-download mcp --stdio`）暴露三个工具：

### `download_video`

解析并保存到本地。

```json
{
  "url": "https://v.douyin.com/xxxx/",
  "output": "~/Downloads/fast-download",
  "name": "可选的文件名",
  "media_type": "video | audio | image"
}
```

| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `url` | 是 | — | 分享链接，或包含链接的整段分享文本 |
| `output` | 否 | `~/Downloads/fast-download` | 输出目录 |
| `name` | 否 | 解析出的标题 | 文件基名 |
| `media_type` | 否 | 自适应 | 取视频 / 音轨 / 图文图片 |

返回：解析结果 + 落盘文件列表（绝对路径、字节数）。

### `parse_video`

只解析，不落盘。

```json
{ "url": "https://v.douyin.com/xxxx/" }
```

返回：`platform`、`title`、`author`、`media[]`（含直链）、`cover_url`、`duration`、`warnings`、`quota`。

### `quota`

无参数。返回当日配额：`plan_id`、`daily_limit`、`used`、`remaining`、`reset_at`。

---

## 手动配置

不想跑安装脚本，就把下面片段自己贴进对应文件。

**Codex** —— `~/.codex/config.toml`：

```toml
[mcp_servers.fast-download]
command = "/Users/you/.local/bin/fast-download"
args = ["mcp", "--stdio"]
```

**Claude Code / Cursor / VS Code（JSON 类客户端）**：

```json
{
  "mcpServers": {
    "fast-download": {
      "command": "/Users/you/.local/bin/fast-download",
      "args": ["mcp", "--stdio"]
    }
  }
}
```

Claude Code 也可以直接：

```bash
claude mcp add -s user fast-download /Users/you/.local/bin/fast-download mcp --stdio
```

> 用**绝对路径**。GUI 启动的 Agent 通常拿不到你 shell 里的 `PATH`，`command: "fast-download"` 在终端里能用、在 Cursor 里就找不到命令。

各客户端配置文件位置见 [`cli.md`](cli.md#接入-agentmcp)，或直接跑 `fast-download setup agent --print` 让它生成。

---

## 行为约定

- **协议通道干净**：stdout 只走 JSON-RPC，诊断信息全部走 stderr；
- **错误是结果，不是崩溃**：工具失败返回 `isError: true` 与结构化 payload，不会杀掉进程；
- **默认落盘目录** `~/Downloads/fast-download`，存在即复用；
- **一次调用一次配额**：`download_video` 内部只解析一次；`parse_video` 与 `download_video` 各算各的。

失败示例：

```json
{
  "ok": false,
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "Run `fast-download auth login` before using this command.",
    "retryable": false,
    "login_command": "fast-download auth login"
  }
}
```

Agent 看到 `login_command` 就知道该让你先登录，而不是瞎猜。

---

## 排查

| 现象 | 原因 | 处理 |
|---|---|---|
| Agent 里没有 `download_video` 工具 | 应用没重启，或配置写到了别的用户目录 | 重启应用；`fast-download setup agent --auto --json` 看写入路径 |
| 工具报 `AUTH_REQUIRED` | key 没保存或已吊销 | `fast-download auth login --key <key>` |
| 工具报 `ENOENT` / 找不到命令 | 配置里写的是相对命令 | 改成绝对路径，或用 `setup agent` 重写 |
| 能解析但下载失败 | 直链过期或网络受限 | 重新解析一次；直链有效期与平台策略相关 |
| 想换账号 | 本地会话还指着旧账号 | `fast-download auth logout` 后重新登录 |

---

## 安全边界

- CLI 只保存会话 token 到 `~/.config/fast-download/config.toml`（`0600`），**不保存你的 Google 密码**；
- 登录在系统浏览器完成，Agent 无法读取输入；
- 给 Agent 用的 key 建议单独创建、单独命名（例如 `agent-cursor`），怀疑泄露时在 <https://fastdown.pro/integrations> 轮换，旧 key 立刻失效；
- 服务端只处理公开链接，不会用你的账号去登录内容平台。
