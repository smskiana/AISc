# NPC 两段式任务队列累计执行记录

> 执行方案：[2026-07-19_NPC两段式任务队列_plan.md](2026-07-19_NPC两段式任务队列_plan.md)
>
> 计划中的独立测试记录：[2026-07-19_NPC两段式任务队列_test.md](2026-07-19_NPC两段式任务队列_test.md)

## 当前结论

阶段 1-5 已实现并通过实现期最低门禁，待独立测试会话统一验收。生产 planner 只生成 `work_tasks / rest_tasks`，Unity 的 `NpcDayPlanRuntime` 已成为唯一日程 owner；旧分钟日程、窗口错过 replan 和互动后整表 replacement 均无生产 caller。复杂任务整体仍不能宣称完成。

## 阶段 1：共享契约与纯逻辑运行时核心

### 前置确认

用户已确认 plan 第 3 节六项推荐值，并明确允许对 `NpcDailyScheduleRuntimeCoordinator` 减重。本阶段只建立减重目标模块，未迁移或修改 coordinator 的生产职责。

### 实际改动

1. `shared/actions.json`
   - 新增唯一 `task_runtime_metadata` 投影表，为正式 action 显式声明 `segment_id`、`completion_policy_id`、`interrupt_policy` 和 `duration_gameplay_seconds`。
   - `work_open / work_close` 标记为 `lifecycle_action`，供后续候选投影排除普通 LLM 队列。
   - `both` 只表示 catalog 兼容范围；进入 `NpcPlannedTask` 后必须落到实际 `work` 或 `rest`。
2. `backend/src/npc/task_catalog.py`
   - 新增 `task_runtime_metadata()` 与 `validate_runtime_metadata()`，统一解析和验证稳定枚举及 duration 正值约束。
   - 未修改 planner、Prompt、parser、fallback 或生产协议。
3. `Assets/Scripts/NPC/NpcDailyScheduleModels.cs`
   - 新增 `NpcDayPlan`、`NpcPlanSegmentDefinition`、`NpcPlannedTask`、`NpcTaskMutation` 和 `NpcDayPlanRuntimeSnapshot` 兼容 DTO。
   - 普通两段式任务不包含 `planned_start_time` 或 execution window 字段。
4. `Assets/Scripts/NPC/NpcDayPlanRuntime.cs`
   - 新增不依赖 `MonoBehaviour`、场景、网络或 executor 的纯 C# 深模块。
   - 封装计划幂等/revision 冲突、匹配终态消费、工作队列提前耗尽、17:00 当前工作续跑/剩余退役、午夜强制终态/清队列、跨日原子替换和状态快照。
   - mutation 由调用方传入协议请求和已经由 catalog 解析的合法任务；runtime 校验 operation 幂等、base revision、当前 segment、candidate 身份和 interrupt policy。成功变更推进 revision，玩家抢占默认退役旧任务。
5. 聚焦测试
   - Python 测试覆盖真实共享 catalog 的元数据完整性、生命周期动作标记和 duration 约束。
   - Unity EditMode 覆盖终态匹配、队列推进、17:00、午夜、revision 冲突、迟到 mutation、不可抢占和 mutation 幂等。

### 实现期最低门禁

1. codebase-memory：执行前新建 `AISc_two_segment_stage1_20260719` moderate 索引，结果 6220 nodes / 19931 edges；实现后更新为 6384 nodes / 20445 edges，并同步 `docs/AIChanges/codebase-memory-mcp_更新.md`。
2. JSON / Python：`python -m json.tool shared/actions.json` 通过；`python -m compileall -q backend/src/npc/task_catalog.py` 通过。
3. pytest：`python -m pytest backend/tests/test_npc_task_semantics.py -q`，6 passed。
4. Unity：通过 Unity MCP 导入 `NpcDayPlanRuntime.cs` 并生成 `.meta`；脚本刷新编译后 Console error 为 0。
5. Unity EditMode：筛选 `NpcDailyScheduleTests`，12 passed / 0 failed / 0 skipped。
6. 静态门禁：`git diff --check` 通过；`python backend/scripts/check_project_conventions.py` 通过。

### 文档与索引回写

已更新 `shared/README.md`、后端/Unity NPC 目录 README、NpcBehavior Workstream 和本目录 README。Workstream 只记录阶段 1 隔离实现，不把两段式队列写成已上线口径。

### 未完成项

1. 尚未创建同主题独立 test record；复杂任务整体不能宣称完成。
2. 真实 provider、完整 day 1/day 2、同日读档、社交暂停恢复和玩家 mutation 生产链仍必须在阶段 6 独立测试会话取证。

## 阶段 2-5：连续实施

用户明确要求连续完成阶段 2-5。执行前评估为上下文负载较低、唯一 plan 边界清晰，故按明确坚持例外连续实施；没有创建第二份 plan，也没有在本会话创建独立 test record。

### 实际改动

1. 阶段 2：候选从共享 catalog 投影 segment/completion/interrupt/duration；Prompt、parser、校验和 fallback 统一为 `work_tasks[] / rest_tasks[]` candidate ID；生产协议切为 `NPC_DAY_PLAN_READY`，普通任务不再携带精确时间、窗口或 miss policy。
2. 阶段 3：`NpcDailyScheduleRuntimeCoordinator` 减重为协议/生命周期适配器，每 NPC 只托管一个 `NpcDayPlanRuntime`；匹配终态才消费，成功/失败/取消都推进；17:00 与午夜边界、schema 3 存档 migration、`day_plan_snapshot` 已接入。
3. 阶段 4：NPC-NPC COMPLETE 与普通玩家对话不再注册整表 replan callback；Unity 删除 context 路由。append/preempt/defer/reject 继续只由 `NpcDayPlanRuntime.ApplyMutation` 的 operation/revision/segment/interrupt policy 边界裁决，未启用新的实时 LLM owner。
4. 阶段 5：删除旧 replan 发送器、后端路由、对话广播和 Unity caller。旧 controller/V1 DTO/tracker 只保留无生产 caller 的迁移/旧测试壳，不进入新存档或 executor owner。
5. Unity MCP 定位 `Town_Main/gameManager_st` 的 `GameTimeController`，将 Test 序列化 `_testDayRealSeconds` 从 300 改为 1200 并保存；回读 1200，`SecondsPerGameMinute=0.8333333`。

### 实现期最低门禁

1. Python `compileall` 通过；聚焦 pytest 24 passed。
2. Unity 脚本刷新后 Console error 0；聚焦 EditMode 37 passed / 0 failed / 0 skipped。
3. `git diff --check` 通过；旧 replan 消息 `rg` 为 0，剩余旧窗口词只在无生产 caller 的兼容策略壳。
4. codebase-memory 更新为 `AISc_two_segment_stage5_20260719` moderate：6372 nodes / 20374 edges，并写出共享 artifact。

### 当前结论

阶段 2-5 实现完成，待阶段 6 独立测试。未进行真实 provider、完整 PlayMode 日内/跨日、真实玩家 mutation 生产链和存档恢复长链验收，因此不得认定整体上线完成。

## 阶段 6 失败修复：Unity 存档 schema 版本收口

### 诊断结论

独立测试记录中的 `PreparingUnity` 悬挂来自 Unity 本地 prepare 同步异常。`GameSaveData.schema_version` 和 `SaveMigrationV2ToV3` 已进入 schema 3，但 `UnitySaveRepository.CurrentSchemaVersion` 仍为 2；`UnitySaveService.Save` 在 `_coordinator.BeginSave` 后调用仓储 `Prepare`，schema 3 快照随即被 `ValidateSaveData` 拒绝，因此事务没有进入 `WaitForMemory`，也没有发送 Python checkpoint prepare。

### 实际改动

1. `UnitySaveRepository.cs`：将仓储当前 schema 从 2 收口为 3，使写入校验与默认 DTO、迁移链终点一致。
2. `NpcDailyScheduleTests.cs`：新增 schema 2 到 3 的迁移回归，以及默认 schema 3 新存档可完成本地 prepare 的回归。
3. `Assets/Scripts/Save/README.md`、`NpcBehavior` 和 `ProtocolAndSave` Workstream：记录三处版本必须同步及当前待复测状态。
4. 新增 schema 演进遗漏错误明细并回写 `ErrorPreventionIndex.md`。

### 实现期最低门禁

1. Unity MCP 强制刷新脚本并请求编译，编辑器恢复 ready；Console error 0。
2. Unity EditMode 筛选 `NpcDailyScheduleTests`：14 passed / 0 failed / 0 skipped，新增 `UnitySaveRepositoryPrepare_AcceptsCurrentSchema` 已执行。
3. `python backend/scripts/check_project_conventions.py` 通过；`git diff --check` 通过，仅输出工作区既存 LF/CRLF 提示。
4. codebase-memory 更新为 `AISc_save_schema_fix_20260719` moderate：6374 nodes / 20408 edges，并写出共享 artifact。
5. 本轮不修改场景、Prefab 或 SerializeField；不需要资产层变更。

### 当前结论

跨日存档 schema 拒绝的实现修复完成，待原 test 记录追加独立复测。真实跨日解除暂停、存档提交、day 2 推进和读档尚未在本执行会话验收，不能宣称两段式任务队列整体上线完成。
