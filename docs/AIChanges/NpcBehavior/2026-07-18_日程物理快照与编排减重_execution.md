# 日程物理快照与编排减重执行记录

> 设计方案: [2026-07-18_日程物理快照与编排减重_plan.md](2026-07-18_日程物理快照与编排减重_plan.md)

## 实际改动

1. 新增 `ScheduleWorldSnapshot` 与有界 `ScheduleWorldSnapshotStore`：严格校验快照 ID、版本单调性和有限枚举；缺失状态保持 `unknown`。
2. `world_snapshot` 接收路径缓存 Unity 提供的 `npc_schedule_physical_state`，开局日程读取最近冻结快照，互动重规划必须引用精确 `snapshot_id/time_revision/world_revision`。
3. Unity 存档快照发送端附加版本化日程物理载荷；地点与 spot 未能从现有 Unity 权威模块取得时明确发送空集合（后端按 unknown 处理），不伪造可用性。
4. 为快照版本拒绝、unknown 语义与 owner 投影增加单元测试。

## 验证

- `python -m unittest backend.tests.test_schedule_world_snapshot backend.tests.test_daily_schedule_planner`：5 项通过。
- Unity MCP 强制刷新与编译完成，Console 无 Error。
- codebase-memory-mcp 已以 moderate 模式重新索引：10979 nodes / 24643 edges。

## 未完成项

`DailyScheduleService` facade 及 `BehaviorEngine` 的完整职责迁移、`aisc_debug` 快照扩展、地点/spot 实时 provider 和 Play Mode 五 NPC 链路尚未完成；本记录仅覆盖本轮已落地的协议冻结与后端校验基础。
