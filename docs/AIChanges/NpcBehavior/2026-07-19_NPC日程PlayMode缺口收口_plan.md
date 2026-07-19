# NPC 日程 PlayMode 缺口收口执行方案

> 问题来源: [DailySchedulePlayModeFindingsDraft.md](../../Workstreams/NpcBehavior/DailySchedulePlayModeFindingsDraft.md)
>
> 计划中的执行记录: [2026-07-19_NPC日程PlayMode缺口收口_execution.md](2026-07-19_NPC日程PlayMode缺口收口_execution.md)
>
> 计划中的独立测试记录: [2026-07-19_NPC日程PlayMode缺口收口_test.md](2026-07-19_NPC日程PlayMode缺口收口_test.md)
>
> 第 13.5.5 条失败后的修复记录: [2026-07-19_NPC日程过期replacement修复_execution.md](2026-07-19_NPC日程过期replacement修复_execution.md)

## 1. 需求理解与结论

本案修复真实 PlayMode 暴露的四类缺口：新游戏误回放上一局日程、运行时 replan 缺冻结快照且重复发送、跨日计划与旧 pending/revision 竞态、真实 planner 输出 5/5 进入 fallback。目标不是取消 fallback，而是先保证生命周期与协议终态正确，再让合法但可修复的模型输出通过统一收口。

四类问题必须按依赖顺序处理：

1. 先建立新游戏与跨日的日程生命周期边界，防止旧状态进入后续 operation。
2. 再补齐 replan 的冻结快照引用、单飞和失败终态，消除每分钟重发及跨 operation 污染。
3. 然后收紧 planner 输入类型并定义有限的规范化策略，保留最终硬校验。
4. 最后用真实供应商和完整 PlayMode 复测；在此之前不能用 fallback 成功代替真实 planner 路径通过。

本案不处理后端自动重连、替代 spot DTO、真实动画完成事件、自然 NPC 社交触发率，也不修改场景、Prefab、SerializeField 或 UI 资产。

## 2. 既定口径

- Workstream：`docs/Workstreams/NpcBehavior/README.md` 的 Unity 运行时权威、冻结 `GameTimeSnapshot`、同日幂等和日程诊断口径。
- 跨域口径：`docs/Workstreams/ProtocolAndSave/README.md` 的 Unity 世界权威与稳定 operation/revision/failure reason。
- ADR：`ADR-0006`。Unity 仍是世界与新游戏生命周期权威；Python 日程快照只是可重建的 AI 运行持久化数据，不升级为世界存档权威。
- 前置方案：日程提交幂等、物理快照、Unity 重规划收口三个既有 plan 保持有效；本案只补真实 PlayMode 发现的遗漏。
- revision 身份明确为 `(game_day, npc_id, schedule_revision)`。允许新游戏日从 revision 1 开始；同一日内才要求 revision 单调递增和相同 revision 内容恒定。

## 3. 工作包 A：新游戏 Python 日程隔离

1. 在 Python 数据层增加显式的日程快照清理 gateway，删除 `npc_daily_schedule_snapshots`，并同步清空 `DailyScheduleService/BehaviorEngine` 的同日内存幂等缓存；不得让 SQL 删除散落在 WebSocket route 中。
2. 将 Unity 新游戏清理请求升级为语义明确的后端新游戏清理 operation。该 operation 统一清理记忆检查点与可重建的日程运行持久化数据，返回匹配 request/operation 的成功或稳定失败码；原 `memory_checkpoints_purge_all` 仅保留兼容入口或迁移后删除，不能继续用名称掩盖扩大后的职责。
3. Unity 只有收到完整清理成功终态后才清本地主存档并进入新游戏；任一子步骤失败均保持加载阻塞，诊断列出失败子域。
4. 同局重连、同日读档和后端进程重启不调用新游戏清理 operation，继续复用同日 snapshot，保证既有幂等语义。
5. SQLite 清理与内存清理必须在同一 service seam 内串行完成；失败不得返回部分成功。若现有存储无法提供事务边界，先增加 repository 事务方法，不在 route 层补偿。

稳定失败码至少包括：`new_game_backend_purge_failed`、`schedule_snapshot_purge_failed`、`memory_checkpoint_purge_failed`。

## 4. 工作包 B：replan 冻结快照、单飞与独立诊断

1. Unity 从最近一次已被后端接受的 `ScheduleWorldSnapshot` 引用中取得 `snapshot_id + time_revision + world_revision`；运行时 replan 不再传空 ID、`-1` 或仅有降级 `physical_state`。如果当前引用缺失，Unity 以 `schedule_snapshot_reference_missing` 本地终态化本次 eligibility，不发送不合法请求。
2. 将 `_replanOperationByNpc: Dictionary<string,string>` 替换为有界 pending 记录，至少持有 `operation_id`、`game_day`、`base_schedule_revision`、`snapshot_id`、请求游戏时间和状态。该状态属于 coordinator，不塞入 `NpcDailyScheduleController`。
3. `RequestReplan` 在创建 operation 前执行 compare-and-set：同一 `(npc_id, game_day, base_revision)` 已 pending 时直接返回 `replan_already_in_flight`，不得生成新 GUID；不同 base revision 到来前必须先终态化旧 pending。
4. 后端在进入 planner 前校验 operation、冻结快照三元组、game day、base revision 和 remaining。所有拒绝都映射为稳定领域码，不向 Unity 暴露 `ValueError/AttributeError` 类型名。
5. 复用现有 `NPC_DAILY_SCHEDULE_READY` 载荷表达 replan 终态：`success/fallback` 才尝试整体替换；匹配 operation 的 `failed/skipped` 只清除 pending、记录 `failure_reason` 并保留原日程。迟到或 operation 不匹配的终态只记录拒绝，不得清理当前 pending。
6. 为 pending 定义 Unity 权威有界超时与显式取消入口。超时只终态化本地 pending 并允许后续重新申请，不要求 Python 监督 Unity；超时值沿用现有协议/供应商上限加固定传输余量，不新增每分钟重试。
7. `schedule_replan_rejected`、超时和稳定失败只写日程诊断；`GameManager` 不再把普通 system message 无条件写入 `WorldPreparationSnapshot.failure_reason`。世界准备只接受匹配其 operation 且属于 world preparation 的进度/失败消息。
8. `interaction_replan_snapshot` 同时显示 Unity pending/terminal 与 backend owner trace；无 backend trace 时保留明确原因，不按 NPC ID 吸附其他 operation。

## 5. 工作包 C：跨日原子换代

1. `NpcDailyScheduleRuntimeCoordinator.Receive` 先按 `game_day` 分支：旧日稳定拒绝；同日执行 revision 幂等；新日进入单一 `ReplaceDayAtomically` seam。
2. `ReplaceDayAtomically` 的顺序固定为：终态化旧日活动日程任务 -> 取消并记录旧 pending replan -> 清除 candidate/request 关联 -> 清除旧 controller 的 remaining/revision/fingerprint -> 接收新日完整计划。中途失败不得留下“新日时钟 + 旧日日程”的混合状态。
3. `NpcDailyScheduleController.TryReplace` 仅在同一 `game_day` 内比较 revision；新日 revision 1 不与旧日 revision 1 比 fingerprint。不同日接收必须经过 coordinator 的原子 seam，controller 不自行猜测跨日副作用。
4. day 1 的 pending operation 永远不能参与 day 2 operation 匹配。恢复存档时若保存日与当前权威日不同，显式丢弃旧 remaining/pending 并请求当前日完整计划。
5. 世界准备只有在目标日全部 NPC 日程进入 accepted、明确 fallback accepted 或稳定失败终态后才能结束；任何 schedule reject 都通过匹配的 world preparation operation 把 `entering_world` 收口为稳定 failed，不允许悬挂。

稳定裁决至少包括：`previous_day_schedule_retired`、`previous_day_replan_cancelled`、`stale_schedule_day`、`next_day_schedule_replace_failed`。

## 6. 工作包 D：planner 输出契约与 required 可满足性

1. `schedule_prompt_adapter.parse_selection` 在访问字段前验证每个数组元素是 object/dict；字符串、数字、null 分别统一收口为 `schedule_item_not_object`，不再泄漏 `AttributeError`。
2. 在候选构建完成、调用 LLM 之前计算 required 候选约束。硬 required 数量不得超过输出上限 10；若业务上可能超过，候选模块必须将其收敛为可满足的必选槽/互斥组，而不是要求模型输出全部 293-301 个候选中的所有 required 项。
3. 明确 required 语义为“必选槽”而非“所有标记项全部出现”：同一职业窗口、routine 或 need 的多个可替代候选进入同一 `required_group_id`，最终校验每组至少命中一个。DTO 保留 candidate ID，Prompt 只渲染组与候选，不从标签文本反推规则。
4. 对模型数组只允许确定性、无语义创造的规范化：按合法 `planned_start_time` 稳定排序；完全重复 candidate/time 去重；非 object、未知 candidate、非法时间、同一时间冲突和 required group 缺失仍整体 fallback。不得自动替模型新增候选或编造时间。
5. `schedule_validation` 在规范化后执行唯一最终硬校验；fallback 也必须通过同一校验。失败诊断使用稳定 `failure_code`，异常类型只可放在有界内部 detail。
6. Prompt 明确 6-10 项、严格时间格式、每个 required group 至少一个，并提供结构化 required group 摘要；候选总量和分组计数继续进入安全 trace。
7. 真实供应商复测若仍大量 fallback，先按稳定 failure code 统计，不继续放宽未知 ID、时间窗、affordance 或物理合法性。

## 7. 预计涉及文件

Python：

- `backend/src/database/sqlite_client.py`
- `backend/src/save/memory_checkpoint.py` 或新增的新游戏后端清理 service
- `backend/src/application/runtime.py`
- `backend/src/application/world_preparation.py`
- `backend/src/npc/behavior_engine.py` / `daily_schedule_service.py`（以实际唯一 owner 为准，不恢复双路径）
- `backend/src/npc/daily_schedule.py`
- `backend/src/npc/schedule_prompt_adapter.py`
- `backend/src/npc/schedule_candidates.py`
- `backend/src/npc/schedule_validation.py`
- `backend/src/npc/schedule_diagnostics.py`
- 对应 `backend/tests/` 聚焦测试

Unity：

- `Assets/Scripts/Save/UnitySaveService.cs`
- `Assets/Scripts/Core/GameCommandSender.cs`
- `Assets/Scripts/Core/GameManager.cs`
- `Assets/Scripts/NPC/NpcDailyScheduleRuntimeCoordinator.cs`
- `Assets/Scripts/NPC/NpcDailyScheduleController.cs`
- `Assets/Scripts/NPC/NpcDailyScheduleModels.cs`
- `Assets/Scripts/Diagnostics/AiscDiagnostics.cs`
- `Assets/Scripts/Diagnostics/DiagnosticModels.cs`
- `Assets/Tests/Editor/NpcDailyScheduleTests.cs` 及相关诊断测试

文档：NPC/Protocol/Save/Diagnostics 目录 README、NPC Workstream、本 plan 对应 execution/test。若实施发现需要场景或资产改动，立即停止并按 Unity MCP 规则另行评估，不纳入本案。

## 8. 实施顺序与最低门禁

1. 先实现 Python/Unity DTO 与稳定失败码测试，确保新旧消息不会被误判为成功。
2. 完成工作包 A，并验证“新游戏清空、同局重连复用”互不冲突。
3. 完成工作包 B，先跑单飞、失败终态和诊断隔离，再继续跨日。
4. 完成工作包 C，验证 day 1 pending + day 2 revision 1 原子换代。
5. 完成工作包 D，先用固定 provider 覆盖解析/规范化/required group，再跑真实 provider 冒烟。
6. 实现会话最低门禁：Python 聚焦 pytest、`compileall`、Unity EditMode 聚焦测试、Unity MCP 编译与 Console 0 error、`git diff --check`。这些结果只允许写“实现完成，待独立测试”。
7. 实现完成后更新 codebase-memory 索引，并同步 `docs/AIChanges/codebase-memory-mcp_更新.md` 的最后更新时间。

## 9. 独立测试方案

独立测试会话按 `docs/Workstreams/TestingAndDiagnostics/README.md` 选择以下最小充分组合：

1. Python 聚焦测试：新游戏清理事务、同日幂等、replan 快照拒绝与稳定码、planner 非 object、required group、排序/去重和 fallback 同校验。
2. Unity EditMode：pending compare-and-set、匹配失败终态清 pending、迟到终态不清当前 pending、跨日 revision 1、原子退役旧任务/operation、world preparation operation 隔离。
3. 白名单 probe：扩展现有 `run_daily_schedule_probe`，覆盖 snapshot reference、single-flight、failed terminal 与 next-day replacement；仍只写 `isolated_in_memory_only`。
4. 真实 PlayMode：执行 findings 草案的全链，使用 `aisc_debug.daily_schedule_snapshot`、`interaction_replan_snapshot`、`runtime_snapshot.world_preparation` 和协议 trace 取结构化证据，Console 只补异常证据。
5. 真实供应商：清理隔离数据后连续生成 5 名 NPC 日程，记录 success/fallback 分布和稳定 failure code；不得保存 Prompt 或模型原文。

## 10. 验收标准

1. 新游戏生成当前 planner version 的全新 day 1 日程；同局重连和同日后端重启只幂等回放。
2. required 窗口过期对同一 NPC/base revision 只产生一个 replan operation；成功、稳定拒绝、超时或取消后 pending 都能终态化。
3. 每个 replan 都携带可由后端精确 `require` 的 snapshot/time/world revision；缺失时不进入 planner。
4. day 2 revision 1 能原子替换 day 1 revision 1，旧 pending/任务/指纹不阻止新日接收。
5. replan 错误不修改已完成的 world preparation failure reason，次日计划失败也不会让 world preparation 停在 `entering_world`。
6. planner 对非 object 输出返回 `schedule_item_not_object`；required 约束在 6-10 项输出范围内可满足；允许的排序/去重规范化后仍经过统一硬校验。
7. 真实 5 NPC planner 不再因当前已知的 `AttributeError`、结构性 required 超量或仅乱序进入 fallback；其他真实业务拒绝必须有稳定 failure code 和可定位 trace。
8. Console 不再每游戏分钟重复 `schedule_replan_rejected:ValueError`；结构化诊断可关联 Unity operation 与 backend owner trace。

## 11. 风险与停止条件

1. 若新游戏清理需要改变 ADR-0006 的权威边界，停止并先更新 ADR；本案只允许清理可重建 Python AI 运行数据。
2. 若 `NpcDailyScheduleRuntimeCoordinator` 因原子跨日和 pending 状态继续显著增重，实施前必须请求用户下达类减重指令，优先拆出 `NpcScheduleReplanTracker` 或等价深模块。
3. 若 required group 会改变策划语义而现有候选数据无法推导互斥关系，停止工作包 D 的该部分，回到独立方案会话确认数据契约；不得凭 action 名称猜组。
4. 若需要新增/修改 Unity 场景、Prefab、SerializeField 或 UI，必须先读取 Unity MCP 使用规则并使用 Unity MCP；不可用时停止修改并请求用户指示。
5. 若真实供应商失败来自业务合法性而非本案四类已知缺口，不继续扩大本 plan，另建有证据的后续方案。

## 12. 独立测试失败后的有界修复执行案

> 修复执行记录：[2026-07-19_NPC日程世界准备终态修复_execution.md](2026-07-19_NPC日程世界准备终态修复_execution.md)

### 12.1 失败结论与根因

独立测试记录已确认：后端午夜维护成功，5 名 NPC 的 day 2 revision 1 日程均已被 Unity 接收，但 `aisc_debug.runtime_snapshot.world_preparation` 仍保留 `phase=entering_world`、`is_active=true`。

代码级定位表明，后端 `WorldPreparationCoordinator.prepare_next_day` 在发送 `MIDNIGHT_SETTLEMENT_COMPLETE` 前已经完成 `_complete`，因此不是 planner、日程接收或后端 world preparation 仍在运行。Unity 的 `HandleWorldPreparationProgress` 会把每个进度包投影为活动快照；新游戏终包 `GAME_READY` 会显式把快照收口为 `complete`，但跨日终包 `MIDNIGHT_SETTLEMENT_COMPLETE` 只恢复 gameplay ready 并转发事件，没有终结匹配 operation 的诊断快照。`MIDNIGHT_SETTLEMENT_FAILED` 当前也只转发事件，没有写入 `failed` 终态。

因此本次失败属于原工作包 C 第 5 条的实现遗漏，不改变原方案边界，不新建第二份 plan。本节是原 plan 的唯一修复补充，后续修复 execution 与复测继续引用本文件和现有失败 test。

### 12.2 修复边界与职责设计

1. 新增纯 C# `WorldPreparationStateTracker`，独立持有当前 `WorldPreparationDiagnosticSnapshot`，负责 `progress / complete / failed` 三类状态转换及 operation 匹配。它不依赖 `MonoBehaviour`、UnityEditor、场景对象或 MCP，可由 EditMode 直接测试。
2. `GameManager` 只保留协议适配：收到 `WORLD_PREPARATION_PROGRESS` 后把 DTO 交给 tracker；收到 `GAME_READY`、`MIDNIGHT_SETTLEMENT_COMPLETE` 或 `MIDNIGHT_SETTLEMENT_FAILED` 后把对应终态交给 tracker，再执行已有 gameplay、UI 和事件转发职责。不得继续在 `GameManager` 内新增分散的快照字段赋值和多组 operation 分支。
3. 活动 operation 必须由进度包建立。`complete/failed` 仅能终结 `operation_id` 与当前活动快照一致的 operation；空 ID 或不匹配的迟到终包不得关闭、覆盖或污染当前 operation。
4. 成功终态固定写入 `phase=complete`、`is_active=false`、`progress_floor=1`、空 `failure_reason`，并保留原 `flow`、`target_game_day` 和匹配 operation ID。
5. 失败终态固定写入 `phase=failed`、`is_active=false`，保留已达到的 `progress_floor`，写入协议稳定 `reason`；不得用异常类型、Console 文本或其他 operation 的错误覆盖当前快照。
6. `GAME_READY` 继续兼容新游戏终态，但也必须经过同一 tracker seam，避免新游戏和跨日形成两套快照收口规则。若 `GAME_READY.operation_id` 的现有 DTO/协议已可用则严格匹配；若缺失，实施会话先核对当前消息契约，只允许为初始世界准备定义有证据的兼容匹配规则，不得无条件关闭任意活动 operation。
7. 本修复不修改 Python world preparation、日程 planner、revision、NPC controller、场景、Prefab、SerializeField、UI 层级或加载视觉设计；也不把“诊断快照完成”等同于自动存档完成或 SleepController 醒来流程完成。

### 12.3 预计涉及文件

- 新增 `Assets/Scripts/Core/WorldPreparationStateTracker.cs`：世界准备诊断状态的唯一 owner 与转换规则。
- 新增或按现有测试组织规范扩展 `Assets/Tests/Editor/WorldPreparationStateTrackerTests.cs`：纯状态机回归。
- 修改 `Assets/Scripts/Core/GameManager.cs`：把进度、成功和失败消息接到 tracker，移除分散快照写入。
- 仅在 DTO 缺少既有 operation 字段时修改 `Assets/Scripts/Data/MessageTypes.cs`；实施前必须先核对后端实际载荷，禁止预防性扩协议。
- 若新增核心入口后目录口径不完整，最小更新对应代码目录 README；不改与本修复无关的 Workstream、ADR 或历史 execution/test 结论。

预计新增 2 个文件并修改至少 1 个运行文件，继续适用原 plan / execution / test 三会话分离规则。`GameManager` 当前已明显过重，本案通过 tracker 移出状态职责，不在其中继续增加多状态、多分支或新依赖。

### 12.4 实施顺序与最低门禁

1. 执行会话先确认 codebase-memory 索引新鲜度，重新读取 `GameManager`、消息 DTO、诊断 DTO 和现有 EditMode 测试的最新内容；若人工修改已触及同一 seam，先处理冲突，不覆盖现有改动。
2. 先以测试固定状态转换契约：进度建立活动 operation、匹配成功终结、匹配失败终结、迟到成功拒绝、迟到失败拒绝、终态后迟到进度不得复活旧 operation。
3. 实现 `WorldPreparationStateTracker`，再把 `GameManager` 的新游戏、跨日成功、跨日失败和进度处理接到唯一入口；保持原事件触发顺序和 SleepController 行为不变。
4. 最低门禁选择 Unity EditMode 聚焦测试、Unity MCP 脚本刷新/编译与 Console 0 error、`git diff --check`。本案没有 Python 行为改动，不机械重复跑 planner pytest；若协议 DTO 或后端载荷发生变化，再增加对应聚焦协议测试。
5. 实现完成后创建互链的后续 execution 记录，只能得出“修复实现完成，待独立复测”；按重大代码更新要求刷新 codebase-memory，并同步其更新时间文档。

### 12.5 独立复测与验收标准

1. 在现有 test 文件追加有界复测记录，不改写原失败证据。先运行 `WorldPreparationStateTrackerTests`，记录通过、失败和跳过数量。
2. 使用真实 Play Mode 从正式 `run_midnight_settlement` 进入 next-day 链；以同一 `operation_id` 证明 `entering_world -> complete`，最终必须为 `is_active=false`、`progress_floor=1`、空 `failure_reason`。
3. 同时确认 `midnight_snapshot.status=success/partial_failure`、目标日 5 份日程已接收、`gameplay_ready=true`，防止只把诊断字段强行改绿而业务链未完成。
4. 使用可控失败 seam 或聚焦测试证明匹配失败终包进入 `failed/is_active=false` 且保留稳定原因；不要求为了造失败污染正式存档或后端数据。
5. 证明旧 operation 的迟到 complete/failed 不会终结新 operation，终态后的迟到 progress 不会把已完成 operation 重新置为 active。
6. Console error 为 0；现有加载遮罩、SleepController 次日推进和自动存档流程无回归。

验收通过后，原验收标准 5 才可由失败改判为通过；其他在现有 test 中标记为“部分通过”的真实互动 replan、同日重启回放等项目不因本修复自动视为已覆盖。

### 12.6 风险与停止条件

1. 若实现发现 `GAME_READY`、午夜成功/失败终包缺少足以关联活动 operation 的协议身份，先停止并在本 plan 中明确最小协议变更；不得通过“关闭最近一次 operation”掩盖协议缺口。
2. 若 tracker 需要接管 gameplay ready、加载 UI、SleepController 或后端业务状态，说明边界已扩大，停止本轮并重新评估，不把多个系统 owner 合并进诊断状态机。
3. 若需要场景、Prefab、SerializeField 或 UI 资产修改，按 Unity MCP 资产优先规则停止代码修复并请求用户指示；当前根因没有资产层证据。
4. 若真实复测中快照已正确 complete 但加载遮罩或睡眠流程仍卡住，应作为新的独立故障定位，不继续扩大本修复。

## 13. 真实 replan 复测发现的冻结快照 revision 污染修复案

### 13.1 失败结论与根因

真实 replan 请求已经取得 `UnitySaveService.AcceptedScheduleSnapshotReference`，其中保存了后端确认的 `snapshot_id / time_revision / world_revision`。但 `GameManager.SendNpcScheduleReplanRequest` 在调用 `GameCommandSender` 时，给 `world_revision` 单独传入持续变化的 `GameManager.WorldRevision`，而 `snapshot_id / time_revision` 来自冻结引用。请求因此混合两个时间点的世界身份，后端 `ScheduleWorldSnapshotStore.require` 按三元组精确校验后稳定拒绝为 `schedule_snapshot_version_mismatch`。

失败终态会按既有规则清除匹配 pending 并保留原日程；窗口已错过的步骤在下一游戏分钟仍满足 replan eligibility，于是再次申请。处理中出现的 `replan_already_in_flight` 是单飞保护的正确裁决，只是被 version mismatch 循环高频触发。后续断线会使现存 pending 无法收到终态并进入 `blocking_message`，但断线恢复不属于本修复的最初根因或实施边界。

本问题是原工作包 B 第 1 条和验收标准 3 的实现遗漏，不改变冻结快照、Unity 世界权威、后端精确校验或单飞语义。本节作为原 plan 的第二个有界修复补充，不创建新的 plan；后续执行与独立复测继续引用本文件。

### 13.2 修复边界与职责设计

1. `NpcScheduleSnapshotReference` 是 replan 快照身份三元组的唯一来源。`snapshot_id`、`time_revision`、`world_revision` 必须从同一个已确认引用一次性投影到 `NpcScheduleReplanRequestCommand`，不得混入 `GameManager.WorldRevision` 或其他当前态 revision。
2. 收紧 `GameCommandSender.SendNpcScheduleReplanRequest` 接口：移除可与 `snapshotReference` 冲突的独立 `worldRevision` 参数，并在命令组装处使用 `snapshotReference.world_revision`。接口层不再允许调用方构造混合三元组，而不是只在当前调用点替换一个实参。
3. `GameManager.SendNpcScheduleReplanRequest` 继续负责取得后端已确认引用并校验引用存在且 `game_day == CurrentTime.day`；调用 `GameCommandSender` 时不再传当前 `WorldRevision`。本修复不向已经过重的 `GameManager` 增加状态、分支、依赖或恢复职责。
4. 保持当前 `GameTime` 传递不变。本案只修复快照身份三元组；若后端另有证据表明 replan 的 `game_time` 也必须冻结到引用创建时刻，应停止并另行确认时间契约，不能在本修复中推断修改。
5. 后端 `ScheduleWorldSnapshotStore.require` 的精确三元组校验保持不变；不得放宽为只校验 `snapshot_id`，也不得在 version mismatch 时回退到 latest snapshot 或当前 world revision。
6. `NpcScheduleReplanTracker` 的 compare-and-set、匹配终态、135 秒超时和跨日取消保持不变。不得通过忽略 `replan_already_in_flight`、缩短 pending 生命周期或为失败步骤加静默冷却来掩盖请求身份错误。
7. 后端断线恢复、`blocking_message` 升级策略和断线时 pending 的终态化属于 `ProtocolAndSave/BackendReconnectFatalDraft.md` 的独立问题，不纳入本修复。

### 13.3 预计涉及文件

- 修改 `Assets/Scripts/Core/GameCommandSender.cs`：删除 replan 发送接口的独立 `worldRevision` 参数，命令字段从同一个 `snapshotReference` 投影完整三元组。
- 修改 `Assets/Scripts/Core/GameManager.cs`：删除调用处的当前 `WorldRevision` 实参，保留既有引用存在性与游戏日校验。
- 新增或扩展 `Assets/Tests/Editor/` 下与命令组装直接相关的聚焦 EditMode 测试：人为设置“当前 world revision != 冻结引用 world revision”，断言序列化请求完整使用冻结引用三元组。实施会话先检查现有可测试 seam；若 `GameCommandSender` 无法在不引入网络/MonoBehaviour 依赖的情况下观察命令，则提取最小纯命令构造 seam，不为单个断言搭建通用协议框架。
- 实现后创建互链的后续 execution 记录；独立复测在现有 `2026-07-19_NPC日程PlayMode缺口收口_test.md` 追加有界记录，不覆盖此前“真实互动 replan 未覆盖”的证据。
- 仅当实现后的代码目录 README 或 Workstream 仍描述 replan 使用当前 world revision 时才做最小文档修正；当前 Workstream 已要求完整冻结三元组，预计无需改口径。

本修复预计修改 2 个运行文件并新增或修改 1 个测试文件，适用 plan / execution / test 三会话分离。本轮不修改消息 DTO、后端 Python、场景、Prefab、SerializeField 或 UI 资产。

### 13.4 实施顺序与最低门禁

1. 新执行会话先确认 codebase-memory 索引新鲜度，读取 `GameManager.SendNpcScheduleReplanRequest`、`GameCommandSender.SendNpcScheduleReplanRequest`、`NpcScheduleSnapshotReference` 和相关测试的最新内容；工作树当前存在同一文件上的既有修改，必须在最新内容上做最小增量，不得覆盖人工或前序实现。
2. 先固定回归用例：冻结引用为 `snapshot_id=s1 / time_revision=2 / world_revision=3`，当前 GameManager 世界 revision 使用不同值，最终命令仍必须是完整的 `s1 / 2 / 3`。
3. 收紧发送接口并修改唯一调用点；静态搜索确认 replan 命令组装不存在第二个独立 world revision 来源，也不存在旧签名调用残留。
4. 实现会话最低门禁选择聚焦 Unity EditMode 测试、Unity MCP 脚本刷新/编译与 Console 0 error、`git diff --check`。本案不改 Python 行为，不机械重复跑 planner 测试；后端既有精确拒绝测试只作为契约证据。
5. 实现完成后刷新 codebase-memory，并同步 `docs/AIChanges/codebase-memory-mcp_更新.md` 的最后更新时间；execution 只能声明“修复实现完成，待独立复测”。

### 13.5 独立复测与验收标准

1. 聚焦 EditMode 回归证明：即使当前 `GameManager.WorldRevision` 已继续增长，replan 序列化载荷的 `snapshot_id / time_revision / world_revision` 仍全部等于同一个 `AcceptedScheduleSnapshotReference`。
2. 使用正式 Play Mode 让 required 日程窗口错过并触发运行时恢复 replan；通过 `protocol_trace` 记录请求 operation 与完整冻结三元组，并与后端已确认 snapshot reference 对齐。
3. 后端接受该三元组并进入 planner/稳定业务终态；协议链不得再出现 `schedule_snapshot_version_mismatch`。若 planner 因其他稳定业务原因失败，必须单独记录，不能视为本修复失败或借机扩大范围。
4. 同一 `(npc_id, game_day, base_schedule_revision)` 在请求处理中仍只能存在一个 pending；额外 Tick 返回 `replan_already_in_flight`，且不得生成第二个 operation ID。
5. 匹配成功或稳定失败终态后 pending 正确释放；成功替换日程后下一分钟不得因原错过步骤再次触发同一循环。若业务稳定失败后原步骤仍持续每分钟重新申请，应记录为独立的 retry/backoff 语义问题，不在本修复中静默改变单飞策略。
6. Console error 为 0；`aisc_debug.daily_schedule_snapshot` 与 `interaction_replan_snapshot` 能关联同一 Unity operation 和后端 owner trace。断线恢复不作为本修复通过的前置条件，但独立复测必须在稳定连接环境完成，避免把无终态与 revision 修复混为一谈。

验收通过后，原验收标准 3 和 8 中“真实 replan 未覆盖”的部分才能改判；自动化通过或 `replan_already_in_flight` 次数下降本身都不能替代真实协议三元组证据。

### 13.6 风险与停止条件

1. 若 `NpcScheduleSnapshotReference` 在发送前可能被原地修改，或 `AcceptedScheduleSnapshotReference` 返回的不是稳定值副本，停止实现并先确认引用不可变/复制语义；不得只调整参数来源后继续允许三元组内部漂移。
2. 若测试需要观察命令而必须改造 `WebSocketClient`、全局网络生命周期或多个发送接口，说明测试 seam 超出本修复边界；先回到方案会话评估最小命令构造抽取，不做通用发送层重构。
3. 若真实复测仍出现 version mismatch，必须对比 Unity 发出三元组与后端 snapshot store 保存值，重新定位 snapshot acceptance/替换时序；不得放宽后端校验。
4. 若实现触及场景、Prefab、SerializeField 或 UI 资产，按 Unity MCP 资产优先规则停止并请求用户指示；当前根因没有资产层证据。
5. 若断线导致 pending 无终态或 `blocking_message` 暂停，转入既有后端重连专项，不继续扩大本修复。

## 14. 会话边界

本文件是唯一实施方案来源。本方案会话到此停止，不修改运行代码。世界准备终态修复已按第 12 节完成并复测；本次 revision 污染修复应在新对话引用本 plan 第 13 节、现有 execution 和 test，先确认 codebase-memory 索引新鲜度并做代码级可行性检查。实现完成后创建互链的后续 execution 记录，再在独立测试对话向现有 test 追加有界复测。
