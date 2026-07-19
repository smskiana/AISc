# NPC 日程世界准备终态修复执行记录

> 唯一执行方案：[2026-07-19_NPC日程PlayMode缺口收口_plan.md](2026-07-19_NPC日程PlayMode缺口收口_plan.md#12-独立测试失败后的有界修复执行案)
>
> 原失败测试：[2026-07-19_NPC日程PlayMode缺口收口_test.md](2026-07-19_NPC日程PlayMode缺口收口_test.md)
>
> 独立复测：[2026-07-19_NPC日程PlayMode缺口收口_test.md](2026-07-19_NPC日程PlayMode缺口收口_test.md#有界复测npc-日程世界准备终态修复)

## 1. 执行结论

已按 plan 第 12 节完成世界准备诊断终态的有界修复。新增纯 C# `WorldPreparationStateTracker` 作为唯一诊断状态 owner，`GameManager` 只做协议适配；新游戏、午夜成功、午夜失败和进度消息统一按 `operation_id` 进入 tracker。

本会话最低门禁通过，只能得出“修复实现完成，待独立复测”。原 test 的真实 Play Mode 失败结论未被改写。

## 2. 实际改动

1. 新增 `Assets/Scripts/Core/WorldPreparationStateTracker.cs`：
   - 进度包建立活动 operation，并按单调下限更新进度。
   - 匹配成功固定收口为 `complete / is_active=false / progress_floor=1`。
   - 匹配失败固定收口为 `failed / is_active=false`，保留已有进度与稳定原因。
   - 拒绝空 operation、活动期间其他 operation 的进度、迟到终包，以及终态后同 operation 的迟到进度。
2. 修改 `Assets/Scripts/Core/GameManager.cs`：
   - `WorldPreparationSnapshot` 改为只读投影 tracker 快照。
   - `WORLD_PREPARATION_PROGRESS`、`GAME_READY`、`MIDNIGHT_SETTLEMENT_COMPLETE`、`MIDNIGHT_SETTLEMENT_FAILED` 接入同一 tracker seam。
   - 保留原 gameplay ready、加载 UI、SleepController 事件转发顺序和职责。
3. 修改 `Assets/Scripts/Data/MessageTypes.cs`：为 `GameReadyMsg` 补齐后端已实际发送的 `operation_id`，未改变后端协议。
4. 新增 `Assets/Tests/Editor/WorldPreparationStateTrackerTests.cs`：覆盖活动建立、匹配成功、匹配失败、迟到成功/失败、终态后迟到进度和活动 operation 并发覆盖拒绝。
5. 更新 `Assets/Scripts/Core/README.md`，登记 tracker 的唯一 owner 边界。

## 3. 最低门禁

选择 Unity EditMode 是因为本次风险集中在纯 C# 状态转换和 operation 匹配；未修改 Python、场景、Prefab、SerializeField 或 UI，因此未机械运行 Python 测试或资产层检查。

| 门禁 | 结果 | 证据 |
|---|---|---|
| Unity EditMode 聚焦测试 | 通过 | `WorldPreparationStateTrackerTests` 7/7 passed，0 failed，0 skipped |
| Unity 编译 / Console | 通过 | Unity MCP 测试触发刷新与编译，Console error 0 |
| `git diff --check` | 通过 | 无空白错误；仅工作树既有 CRLF 提示 |

## 4. 索引与文档回写

- 更新 `Assets/Scripts/Core/README.md` 与 `docs/AIChanges/NpcBehavior/README.md`。
- 实现前建立新鲜 codebase-memory 项目 `AISc_world_prep_fix_20260719` 并抽查目标调用链；实现后再次刷新并同步 `docs/AIChanges/codebase-memory-mcp_更新.md`。
- ADR-0006、NpcBehavior Workstream 与 ProtocolAndSave 口径仍一致，无需修改。

## 5. 未完成项

1. 尚未执行 plan 第 12.5 节的真实 Play Mode 跨日复测。
2. 尚未向原 test 追加 `entering_world -> complete`、稳定失败和迟到 operation 的独立证据。
3. 原 test 中真实互动 replan、同日后端重启回放等未覆盖项继续保持未覆盖，不因本修复自动通过。

## 6. 独立复测状态

独立复测已通过：`WorldPreparationStateTrackerTests` 7/7，真实 next-day operation `world_prepare_1217dcbcb6db476784cd632016d9232e` 从活动态收口为 `complete / is_active=false / progress_floor=1 / failure_reason=""`；5/5 day 2 revision 1 日程、midnight success、gameplay ready、加载暂停释放、存档 Idle 与 Console 0 error 同时成立。完整证据追加在原 test 的“有界复测”章节。
