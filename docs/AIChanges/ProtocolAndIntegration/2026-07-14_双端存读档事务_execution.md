# 双端存读档事务执行记录

> 设计方案: [plan.md](2026-07-14_双端存读档事务_plan.md)

## 实际改动

1. Python `AppServices` 接入 `MemoryCheckpointService`，新增四类 envelope handler。
2. Unity 新增 `UnitySaveService`，协调本地主存档和 Python 记忆检查点。
3. `GameStateStore` 可导出 / 应用稳定世界存档 DTO。
4. `GameManager` 只保留 facade 和旧 UI 事件桥接。

## 验证

1. Python 全套 26 项测试通过。
2. Python compileall 通过。
3. Unity MCP 强制导入新脚本后编译通过，Console 0 error。

## 已知边界

存档列表仍使用旧 Python 列表入口；将在状态迁移批次切换为 Unity 本地 manifest。
