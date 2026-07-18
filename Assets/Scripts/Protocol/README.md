# Protocol 脚本目录

## 文件夹功能

负责 Unity 侧协议 envelope、版本、连接 session、sequence、错误解析和重连握手。

## 文件夹内容

`ProtocolClient` 位于 `WebSocketClient` 与业务消息路由之间。业务命令由 `GameCommandSender` 构造，不应直接管理协议 sequence。

`ProtocolClient` 同时保留最近 200 条 envelope 元数据诊断轨迹，可通过项目专用 Unity MCP 工具 `aisc_debug` 的 `protocol_trace` action 读取。轨迹不保存完整 payload。
