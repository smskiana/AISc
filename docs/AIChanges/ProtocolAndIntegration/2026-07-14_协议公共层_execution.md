# 协议公共层执行记录

> 设计方案: [plan.md](2026-07-14_协议公共层_plan.md)

## 实际改动

1. Python 新增 protocol codec、session、统一错误和幂等结果缓存。
2. WebSocket 入口为每个连接创建独立 `ProtocolSession`。
3. 新增 `hello / hello_ack` envelope 握手，并保留旧扁平消息兼容。
4. Unity 新增 `ProtocolClient` 和协议 DTO，在连接建立后自动握手。
5. 通过 Unity MCP 安装官方 `com.unity.nuget.newtonsoft-json@3.2.1`。

## 验证

1. `python -m unittest backend.tests.test_protocol_foundation -v`: 5 项通过。
2. `python -m compileall -q backend/src backend/tests`: 通过。
3. Unity MCP 域重载完成，Console 无新增 C# error。

## 已知边界

1. 旧业务消息仍使用扁平 JSON，后续按消息族迁移。
2. 幂等缓存已提供基础能力，保存 / 加载批次再正式接入副作用命令。
