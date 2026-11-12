# MCP 配置片段

这些片段用于**手动**接入。正常情况下不需要手写 —— 跑一次即可自动写入所有检测到的客户端：

```bash
curl -fsSL 'https://fastdown.pro/mcp?key=<connect-key>' | sh
```

或本地已装 CLI 时：

```bash
fast-download setup agent --auto       # 写入
fast-download setup agent --print      # 只打印，不动文件
```

## 文件对应关系

| 客户端 | 配置写法 | 文件位置 |
|---|---|---|
| Codex | TOML (`[mcp_servers.fast-download]`) | `~/.codex/config.toml` |
| Claude Code | `claude mcp add -s user ...` | 失败时回退 `~/.claude.json` |
| Cursor | JSON (`mcpServers`) | `~/.cursor/mcp.json` |
| VS Code | JSON (`mcpServers`) | `<user-data>/Code/User/mcp.json` |
| OpenCode | JSON | `~/.config/opencode/opencode.json` |
| Gemini CLI | JSON | `~/.gemini/settings.json` |
| Windsurf | JSON | `~/.codeium/windsurf/mcp_config.json` |

- `codex.toml` —— Codex 的片段；
- `claude.json` —— Claude Code / Cursor / VS Code 等 JSON 类客户端通用的 `mcpServers` 片段。

## 两个容易踩的坑

1. **必须用绝对路径**。GUI 启动的 Agent 拿不到你 shell 的 `PATH`，写 `"command": "fast-download"` 会报找不到命令。
2. **改完要重启客户端**。多数 Agent 只在启动时读一次 MCP 配置，热重载不生效。

接入后工具说明见 [docs/mcp.md](../../docs/mcp.md)。
