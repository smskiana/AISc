# 外界感知日程与互动重规划执行记录

> 设计方案: [2026-07-17_外界感知日程与互动重规划_plan.md](2026-07-17_外界感知日程与互动重规划_plan.md)

## 本次实际改动

1. `DailySchedulePlanner` 的受控 JSON 选择增加计划数量约束：候选可用数量足够时必须为 6-10 条；未知候选、无效时间、重复时间和非单调时间仍会整体 fallback。
2. fallback 生成会把默认开始时间碰撞按 30 分钟递进修复，保证输出仍满足严格单调的 `HH:MM` 契约。
3. `BehaviorEngine.replan_from_unity_request()` 与 runtime `NPC_SCHEDULE_REPLAN_REQUEST` 路由已接通。请求显式携带冻结 `game_time`、`world_revision`、Unity 权威剩余日程与 base revision，返回完整 `NPC_DAILY_SCHEDULE_READY` 替换结果。
4. Unity `NpcDailyScheduleController` 增加仅保存剩余日程的导出/恢复/跨日清理接口；临时 pending 与 in-flight 不进入存档。
5. `GameStateStore` 通过注册式 bridge 接入 `NpcSpawner`，Unity 主存档现会写入并在读档时恢复 `schedule_day`、revision、planner version 和 remaining schedule。不同游戏日的旧日程被明确丢弃并等待正式重新生成。
6. `aisc_debug` 增加只读 `daily_schedule_snapshot`，提供 Unity 接收的日程 revision、剩余数量、pending candidate 和最近裁决原因。
7. Unity 任务终态改用非阻塞 `NPC_RUNTIME_EVENT` 同步；Python 对该消息仅作有界幂等记录，不再依此启动、重试或监督任务。旧 `NPC_ACTION_RESULT / NPC_TASK_STATUS` 只保留兼容拒收 ACK，正式链路已删除任务监督源码。
8. 新增 Unity `NpcSocialCandidateController`：以 Unity 权威分钟扫描同 zone、玩家同 zone、未移动、未锁定且非 transit 的 NPC 对；Python 仅返回 `NPC_SOCIAL_DECISION_RESULT`，结果到达后 Unity 再校验 world revision 与物理条件，成功才进入既有会合协议，并仅此时写入 Unity 冷却。
9. 删除 `BehaviorEngine` 中遗留的 `_tick_npc()`、`_check_social_opportunities()`、`_send_behavior()`、`handle_action_result()`、`handle_task_status()`、`poll_task_nodes()` 和 `task_tracker.py`；`BehaviorEngine` 现在只保留日程、重规划 facade、社交语义和上下文摘要。
10. 新增 Unity `NpcRuntimeStateController`，迁移 P0 睡眠、need、energy、sociability、current_need 和 asleep 推进；运行时状态写入 Unity 主存档，并进入 `aisc_debug.runtime_snapshot / npc_runtime_state_snapshot`。
11. `StateManager.apply_interaction_effect()` 改为返回 `NPC_STATE_EFFECT`，只继续维护 Python 权威的印象/记忆，不再直接更新 `npc_states` 运行时世界字段。Unity 按 `base_world_revision` 应用或拒绝迟到 effect。
12. 玩家正常对话和 NPC-NPC 对话 COMPLETE 后都会发送 `NPC_SCHEDULE_REPLAN_CONTEXT`；Unity 收到后按受影响 NPC 的权威剩余日程、当前 schedule revision、物理状态和 world revision 发起 `NPC_SCHEDULE_REPLAN_REQUEST`。
13. `NpcDailyScheduleController` 的 `RequestReplan` 裁决现在会实际触发 Unity 权威重规划请求，不再只停留在诊断原因。
14. 修复现场发现的龙之介工作地点越界：`work_*` 任务在 `NpcTaskCatalog` 层限制到 NPC 自己负责的职业 zone，避免仅凭 `shop_service` tag 把和菓子店工作派到面包店 counter。
15. 修复 Unity 社交候选协议边界：`NPC_SOCIAL_DECISION_RESULT` 只代表后端语义意愿，Unity 不再本地伪造 `NpcSocialPrepareMsg` 启动会合；后端在语义接受后正式登记 `NpcSocialSessionCoordinator` session 并下发 `NPC_SOCIAL_PREPARE`。
16. 修复社交候选 pending 洪泛：Unity 扫描器现在按无方向 NPC pair 记录未决候选，同一 pair 未收到语义结果时不再每个权威分钟重复发送；超过 3 个游戏分钟未返回则释放 pending，避免后端被重复候选压住而迟迟没有 PREPARE/气泡。
17. 社交冷却写入从“语义 true 后立即写”后移到 Unity 收到正式 `NPC_SOCIAL_PREPARE` 且本地玩家对话/物理条件仍通过之后，避免出现“写了冷却但后端没有正式 session”的吞候选状态。

## 验证

- `python -m pytest backend/tests -q`
- 结果：`94 passed, 3 subtests passed`。减少的用例为已删除的旧 `TaskTracker` / `BehaviorEngine._send_behavior` 监督路径测试。
- `dotnet build Assembly-CSharp.csproj --no-restore -v:q`
- 结果：成功生成，0 error；保留项目既有的程序集版本与未赋值字段警告。
- Unity MCP Play Mode 现场诊断：原快照确认 Day 1 12:21 玩家、千早、龙之介同在 `bakery.counter`，龙之介任务为 `work_tend -> bakery.counter`；修复后新局快照确认龙之介工作任务落在 `wagashi.back_workbench`，千早工作任务落在 `bakery.*`。手动同屏偶遇探针确认社交扫描 pending 从现场的 304 个重复候选收敛为单 pair 1 个 pending，随后释放，不再洪泛。
- Unity MCP Play Mode 探针：成功进入 Play Mode 请求并读取 Console，Console 当前 0 条错误；但 MCP 执行域中 `Application.isPlaying` 与 editor state 的 Play Mode 状态不一致，未能可靠完成存读档、跨日、社交锁和完整对话重规划长链验证。
- 新增 EditMode 覆盖：`NpcRuntimeStateControllerTests` 验证 `NpcStateEffect` base revision 过期拒绝、匹配应用和 Unity P0/need tick。

## 剩余风险与后续验证

旧 `BehaviorEngine` 物理 tick、后端 NPC-NPC 物理扫描和 `TaskTracker` 监督源码已删除；Unity P0/need/运行时状态、`NpcStateEffect`、玩家/NPC-NPC 互动后重规划闭环和诊断 DTO 已接入。

现场 bugfix 后，职业工作任务已限制到角色自己的店铺 zone；NPC-NPC 偶遇必须经过“Unity 物理候选 → 后端语义意愿 → 后端正式 PREPARE → Unity READY/FAILED → 后端气泡/COMPLETE”闭环，不再允许 Unity 本地伪造社交 session。当前探针仍不能保证每次同屏都聊天，因为语义意愿可返回 false；这属于概率行为，不再等同于协议未触发。

仍需在 Unity 编辑器 Play Mode 稳定运行时补做完整端到端验证：新游戏、玩家对话结束、NPC-NPC COMPLETE、存读档、跨日、社交锁 defer/request_replan、迟到 effect 拒绝和 `aisc_debug.npc_runtime_state_snapshot`。本轮未触碰场景、Prefab、SerializeField 或 UI 资产。
