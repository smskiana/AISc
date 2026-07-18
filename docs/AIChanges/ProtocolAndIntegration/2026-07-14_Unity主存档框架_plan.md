# Unity 主存档框架设计方案

> 执行记录: [execution.md](2026-07-14_Unity主存档框架_execution.md)

## 需求理解

建立独立于 `GameManager` 的 Unity 主存档模型、磁盘仓储、schema migration 和双端协调状态机，为后续事务协议提供本地基础。

## Workstream / Roadmap

- Workstream: `ProtocolAndSave`
- Roadmap item: Unity 主存档框架
- 相关 ADR: ADR-0006
- 工程口径变化: Unity 开始拥有正式世界存档格式

## 实现方案

1. `GameSaveData` 保存当前已有的时间、天气、玩家地点和 NPC 世界状态。
2. `UnitySaveRepository` 使用临时目录、SHA-256 和原子替换。
3. `SaveMigrationRegistry` 通过有序 migration 接口扩展，不使用大型 switch。
4. `SaveCoordinator` 只管理保存 / 加载阶段，不承担 UI 或磁盘细节。
5. 不保存对话、移动过程、UI、动画和连接状态。

## 验证

通过 Unity MCP 编译、Console 检查，并为纯 C# 仓储补最小 EditMode 测试入口（若现有测试程序集可用）。
