# 日程提交幂等与重连恢复执行记录

> 设计方案: [2026-07-18_日程提交幂等与重连恢复_plan.md](2026-07-18_日程提交幂等与重连恢复_plan.md)

## 实际改动

1. `backend/src/database/sqlite_client.py` 新增 `npc_daily_schedule_snapshots` 表及读写接口，保存 `game_day`、NPC、revision、完整 DTO 指纹、planner/operation、状态和 JSON 载荷。
2. `backend/src/npc/behavior_engine.py` 的 `ensure_daily_plans()` 在进程内缓存未命中时先恢复同日完整快照；恢复后以 `idempotent_replay` 重发，不调用 LLM。新生成和互动重规划结果均持久化，并补充稳定 payload fingerprint、status、failure_reason 协议字段。
3. Unity `NpcDailyScheduleController` 拒绝 `failed/skipped` 非权威结果及旧游戏日迟到结果，记录 operation/fingerprint；`NpcDailyScheduleReadyMsg` 与 `NpcDailyScheduleDiagnosticSnapshot` 暴露对应字段。

## 验证

- `python -m pytest backend/tests/test_daily_schedule_planner.py backend/tests/test_world_preparation.py -q`：7 passed。
- `python -m compileall -q backend/src`：通过。
- `git diff --check`：通过。

## 未完成与风险

- Unity Editor Play Mode 已完成真实长链：后端重启导致断线，随后通过现有 `WebSocketClient.BeginConnect(forceRetry=true)` 重连；恢复后 health 为 `ready`，协议重新协商成功，日程仍为 `game_day=1 / revision=1`，未出现 `revision_content_conflict`。
- 同日保存后立即读档成功；读档后仍为 `day=1 / revision=1`，剩余日程按保存时消费状态恢复，未重新生成计划。
- 当前客户端在后端异常关闭时不会自动调用 `BeginConnect`，会出现 `WebSocketClient.cs:340` 的接收循环异常并进入 `blocking_message`；必须使用开始界面的重试入口或显式重连调用。该项是现有重连 UX/策略缺口，未在本轮擅自扩展代码范围。
- 本轮未修改场景、Prefab 或资产连线；Unity 与后端的 revision 对账通过现有重发协议完成，未新增独立查询消息。
