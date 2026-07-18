# codebase-memory-mcp 配置恢复执行记录

> 设计方案：未创建 plan；本轮为 Codex 本机 MCP 配置缺失的局部修复，按小修处理。

## 需求

排查重启 Codex 后仍没有 codebase-memory-mcp 工具的原因，并恢复对应 MCP 配置。

## 原因

`%USERPROFILE%/.codex/config.toml` 当前内容中缺失 `[mcp_servers.codebase-memory-mcp]` 配置段；`%USERPROFILE%/.local/bin/codebase-memory-mcp.exe` 本身存在且 `--version` 返回 `0.9.0`，因此问题不是二进制损坏，而是 Codex MCP 配置丢失。

## 实际改动

1. 在 `%USERPROFILE%/.codex/config.toml` 加回 `[mcp_servers.codebase-memory-mcp]`。
2. 配置 stdio MCP 命令为 `%USERPROFILE%/.local/bin/codebase-memory-mcp.exe`。

## 验证

已验证本机二进制 `codebase-memory-mcp.exe --version` 输出 `codebase-memory-mcp 0.9.0`。

本轮不涉及运行时代码、Unity 场景 / Prefab / SerializeField 连线、诊断钩子或控制钩子。
