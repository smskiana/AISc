# codebase-memory-mcp 索引刷新执行记录

> 设计方案：未创建 plan；本轮为用户要求的辅助索引刷新和单文件状态记录更新，按小修处理。

## 需求

刷新当前项目 `F:/GameProject/unity/AISc` 的 codebase-memory-mcp 索引，并同步 `docs/AIChanges/codebase-memory-mcp_更新.md` 的最近更新时间。

## 实际改动

1. 执行 `codebase-memory-mcp cli index_repository` 刷新项目索引库。
2. 更新 `docs/AIChanges/codebase-memory-mcp_更新.md` 的最近更新时间。
3. 在状态文件中补充最近索引结果 `10744 nodes / 23921 edges`。

## 验证

索引命令返回 `status=indexed`，节点数 `10744`，边数 `23921`，跳过文件数 `0`。

本轮不涉及运行时代码、Unity 场景 / Prefab / SerializeField 连线、诊断钩子或控制钩子。

## 后续完整刷新（2026-07-18 08:37 +08:00）

按用户要求再次以 `full` 模式刷新索引，并写出 `.codebase-memory/graph.db.zst` 共享产物。结果为 `10850 nodes / 24153 edges`，`skipped_count=0`，工具返回 `status=indexed`。
