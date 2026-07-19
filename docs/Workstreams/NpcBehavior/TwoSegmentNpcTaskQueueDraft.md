# NPC 两段式任务队列草案

## 文档状态

本文记录 NPC 日程从“精确时间点日程”迁移为“两段式顺序任务队列”的实施前设计草案，并附带建议执行阶段。

本文不是 implementation plan，不授权修改运行代码、协议、场景、Prefab、SerializeField 或测试资产。确认实施后，应另开方案会话创建唯一 plan；后续实现与独立测试继续遵循 plan / execution / test 三会话分离规则。

## 1. 背景与问题

当前系统让 LLM 为每项任务输出 `planned_start_time`，Unity 使用统一的 `execution_window_before_minutes / execution_window_after_minutes` 判断任务是否可执行。默认窗口为 `±30` 游戏分钟；required 项错过窗口后触发整份 replacement replan，非 required 项被跳过。

真实 PlayMode 已证明该模型存在结构性冲突：

1. Test 时间档一天 300 秒，30 游戏分钟只相当于 6.25 秒；真实供应商单 owner 常耗时约 8-10 秒。
2. replan 使用请求冻结时间生成 replacement，但生成期间 Unity 游戏时间继续推进；结果到达时可能已经再次过期。
3. required candidate 会被 deterministic fallback 重新选中，只是顺延到请求时刻，不能表达“开店任务已经错过，应退役或切换语义”。
4. Unity 接收 replacement 时校验 operation、day 和 revision，但不校验结果在应用时是否仍可执行。
5. 成功 replacement 可能立即触发下一次 replan，revision 与 pending 持续增长；单飞只能阻止并发，不能终结循环。
6. 当前设计文档要求 `fixed / flexible / opportunistic + valid_window + miss_policy`，实际运行结构仍主要依赖单一时间点与统一窗口。

因此本草案不继续扩大统一时间窗口，而是移除普通任务的精确发生时间，把“是否继续做下一件事”交给 Unity 权威任务终态和阶段边界。

## 2. 目标与非目标

### 2.1 目标

1. 每名 NPC 每天只有一份 `NpcDayPlan`，包含工作和休息两个有序任务队列。
2. LLM 只选择和排序合法 candidate，不输出普通任务的精确 `HH:MM`。
3. Unity 在当前任务终态后自动取出下一候选并执行，不再按游戏分钟追赶任务时间点。
4. 08:00、17:00 和午夜只负责阶段转换与边界裁决，不为每个普通任务建立窗口。
5. NPC-NPC 对话不重建当日任务表；对话结束后恢复原任务或继续原队列。
6. Player-NPC 对话可以产生一个受控任务变更：追加、抢占、延后或拒绝。
7. 未来其他 LLM 实时决策复用同一任务变更 interface，不新增第二套抢占路径。
8. Test 时间档改为现实 20 分钟一天，便于观察移动、动作、对话、抢占与阶段转换。

### 2.2 非目标

1. 不允许 LLM 自由生成 action、location、spot 或完成条件。
2. 不把任务成功、失败、取消或强制终态的裁决权移到 Python。
3. 不在本案中实现真实动画、交易、经营、送礼或其他玩法完成事件。
4. 不用扩大统一宽限窗口保留旧 `planned_start_time` 模型。
5. 不让 NPC-NPC 对话直接插入新任务；其记忆和关系影响下一日计划。
6. 不修改 Unity 世界权威、Python 记忆权威和冻结 world snapshot 三元组边界。

## 3. 领域模型

### 3.1 DayPlan

`NpcDayPlan` 是单个 NPC、单个游戏日的完整计划身份：

```text
NpcDayPlan
  npc_id
  game_day
  plan_revision
  planner_version
  work_tasks[]
  rest_tasks[]
  evidence / trace summary
```

同一 `(npc_id, game_day, plan_revision)` 的内容必须恒定。新日通过原子换代入口退役旧计划、旧活动任务、旧任务变更 pending 和旧关联。

### 3.2 PlanSegment

首版只启用两个 segment，但实现使用统一定义而不是为两类写散落的 if/else：

| segment_id | 游戏时间 | 进入规则 | 退出规则 |
|---|---|---|---|
| `work` | 08:00-17:00 | 世界准备完成后启用工作队列 | 17:00 触发工作边界 |
| `rest` | 17:00-24:00 | 工作活动任务终态后启用休息队列 | 午夜触发日终边界 |

建议由 `NpcPlanSegmentDefinition` 表达 `segment_id / starts_at / ends_at / boundary_policy`，为未来节日、营业班次或特殊事件预留扩展位。

### 3.3 PlannedTask

```text
NpcPlannedTask
  task_id
  candidate_id
  action_id
  location_id
  target_person_id?
  segment_id
  completion_policy_id
  interrupt_policy
  source
  evidence_ids[]
```

普通任务不再携带：

- `planned_start_time`
- `execution_window_before_minutes`
- `execution_window_after_minutes`
- `miss_policy=request_replan`

地点营业时间、天气、可达性和 spot 可用性仍是 candidate 合法性，不等同于任务执行时间点。

### 3.4 TaskMutation

Player-NPC 对话和未来实时 LLM 决策只返回一个有界任务变更：

```text
NpcTaskMutation
  operation_id
  npc_id
  base_plan_revision
  source_type
  mutation_type
  candidate_id
  requested_segment
  reason
```

首版 `mutation_type`：

- `append_after_current`
- `preempt_current`
- `defer_until_current_terminal`
- `reject`

变更只能引用正式候选；Unity 必须重新校验目标、位置、玩法状态、当前 segment、revision 和 interrupt policy。

## 4. 两段式生成契约

### 4.1 单 owner 单次 LLM

每天仍保持每名 NPC 一次 LLM 调用，一次结果同时返回两个队列；不得拆成工作一次、休息一次，避免 5 名 NPC 从 5 次调用扩大到 10 次。

建议输出：

```json
{
  "work_tasks": [
    { "candidate_id": "..." },
    { "candidate_id": "..." }
  ],
  "rest_tasks": [
    { "candidate_id": "..." },
    { "candidate_id": "..." }
  ]
}
```

LLM 不输出持续时间、完成条件、可抢占性、移动方式或失败策略。这些字段由任务目录按 `action_id` 投影。

### 4.2 候选分段

候选的 `segment_id` 必须来自结构化 action/task catalog 元数据，不得根据 action 名称在 planner 中猜测。初始建议：

- `work`：职业生产、开店期间服务、清洁、制作、巡逻和工作 routine。
- `rest`：吃饭、休息、散步、拜访、个人兴趣和睡眠。
- `both`：经领域确认可跨段的通用任务，由 planner 投影到一个实际 segment，不能同时复制到两边。

`work_open / work_close` 不再作为普通 LLM 队列任务。它们应由工作 segment 的 enter/exit 生命周期确定性处理，避免队列拥堵导致商店永远不开或不关。

### 4.3 硬校验

最终校验至少保证：

1. 两个数组存在且条目数在配置范围内；队列允许提前耗尽，不承诺所有任务都会执行。
2. candidate ID 存在、segment 兼容、地点合法且物理过滤通过。
3. 同一队列不重复 candidate；跨队列重复只在 catalog 明确允许时接受。
4. 必要职业职责进入工作队列；基础 need 进入休息队列或由 Unity P0 状态模块接管。
5. `work_open / work_close` 不出现在 LLM 队列。
6. fallback 与 LLM 结果经过同一个最终校验。

### 4.4 Fallback

fallback 分别为两个 segment 选择有序 candidate：

1. 工作段先选职业核心职责，再选 routine 和附近低成本工作。
2. 休息段先保证基础 need，再选个人活动、关系活动和附近低成本活动。
3. 不生成时间点，不通过“一分钟递增”伪造可执行性。
4. 不把已经完成、当日已退役或当前物理状态明确不可行的 candidate 重新加入。

## 5. Unity 运行时深模块

建议新增或重构为 `NpcDayPlanRuntime` 深模块，由它独立持有 segment、队列、活动计划任务、边界裁决和任务变更。`NpcDailyScheduleRuntimeCoordinator` 不应继续吸收这些新状态和分支；实施前应按项目类减重规则取得用户的“减重”指令，再迁移现有职责。

建议 seam 保持精简：

```text
AcceptPlan(plan)
OnTaskTerminal(terminal)
OnSegmentBoundary(boundary)
ApplyMutation(mutation)
CreateSnapshot()
```

调用方不应手工执行“消费队首 -> 选择 segment -> 丢弃剩余 -> 启动下一任务”等多步编排；这些行为由模块实现封装。

### 5.1 队列推进

1. 当前没有活动任务时，从活动 segment 队首取出一项。
2. Unity 再次校验 NPC、action、location、spot、segment 和玩法状态。
3. 合法则交给现有 `NpcTaskExecutor` 执行“移动 -> 动作 -> 终态”。
4. `succeeded / failed / cancelled / forced_terminal` 都消费当前计划任务并记录稳定原因。
5. 当前任务终态后自动取下一项；任务失败不触发完整 LLM replan。
6. 若存在确定性替代 spot，可在同一任务内尝试一次；没有替代则消费并继续队列。

### 5.2 工作边界 17:00

| 状态 | 裁决 |
|---|---|
| 无活动工作任务 | 丢弃剩余工作队列，立即进入 rest |
| 活动工作任务未完成 | 允许当前任务继续，丢弃其余工作队列 |
| 活动工作任务随后终态 | 进入 rest 并取休息队首 |
| rest 队列为空 | 进入受控 idle/ambient，不请求新计划 |

工作边界稳定原因：

- `retired_at_work_segment_end`
- `work_task_continues_after_segment`
- `rest_segment_started`

### 5.3 午夜边界

| 状态 | 裁决 |
|---|---|
| 活动休息任务未完成 | 以 `completed_by_day_boundary` 强制终态 |
| 剩余休息队列非空 | 全部以 `retired_at_day_end` 退役 |
| 队列为空 | 直接进入日终 |
| 活动工作任务异常跨到午夜 | 使用稳定强制终态，不允许永久阻塞午夜 |

完成边界收口后，Unity 才请求午夜结算。午夜结算不等待 Python 监督 Unity 任务，也不把退役任务伪装成正常业务成功事件。

## 6. 任务完成与抢占

### 6.1 CompletionPolicy

完成策略由任务目录声明：

| policy | 适用任务 | 终态来源 |
|---|---|---|
| `duration` | 默认工作、休息表现 | Gameplay 时间域累计达到持续量 |
| `animation_event` | 正式动画动作 | 动画完成事件 |
| `interaction_result` | 交易、制作、玩法交互 | 玩法结果 |
| `state_condition` | 到达或状态变化 | Unity 权威状态条件 |
| `segment_boundary` | 允许在日终收口的休息表现 | 阶段边界 |

默认 `duration` 必须使用 Gameplay 时间域，暂停游戏时不继续完成；不得直接沿用缺少领域语义的固定 `expected_duration_sec=1`。

### 6.2 InterruptPolicy

首版建议：

- `non_interruptible`：当前任务完成后再执行变更。
- `player_interruptible`：仅玩家任务可抢占。
- `fully_interruptible`：玩家任务和未来实时 LLM 都可抢占。

抢占必须产生旧任务稳定终态，例如 `preempted_by_player` 或 `preempted_by_runtime_decision`，并明确旧任务是退役、回队首还是回队尾；默认退役，不隐式重复执行。

## 7. 对话语义

### 7.1 NPC-NPC 对话

1. NPC-NPC 对话完成后不发送日程 replan context，不生成 replacement。
2. 社交 session 仍由 Unity 负责 reservation、真实会合、播放、超时和终态释放。
3. 若社交只在空闲或可中断状态建立，当前计划任务按 interrupt policy 暂停或终态化。
4. 对话结束后恢复暂停任务或继续队列；具体策略必须由同一运行时模块裁决。
5. 对话摘要和关系变化进入记忆，影响下一日 LLM 计划。

### 7.2 Player-NPC 对话

1. 普通聊天结束不自动重建整日计划。
2. 只有对话内容产生明确、合法且被 NPC 接受的玩家安排时，后端才返回 `NpcTaskMutation`。
3. 每次对话终态首版最多产生一个 mutation，避免一次对话无限扩张队列。
4. `preempt_current` 必须通过 Unity 当前任务 interrupt policy；不能抢占时降级为 `defer_until_current_terminal` 或稳定拒绝。
5. 玩家安排任务完成后继续当前 segment 的原队列；不重新生成另一 segment。

### 7.3 未来实时 LLM

未来实时行为决策复用 `NpcTaskMutation`，但 `source_type`、权限和冷却独立配置。不得绕过 Unity 队列运行时直接调用 `NpcTaskExecutor.Execute`，否则会恢复多 owner 抢占。

## 8. 协议、revision 与持久化

### 8.1 计划协议

日计划 replacement 从平铺 `items[]` 迁移为 `segments` 或明确的 `work_tasks / rest_tasks`。迁移期间可暂时双读，但生产 owner 必须只有一个；完成迁移后删除 `planned_start_time` 生产依赖。

计划仍携带：

- `operation_id`
- `npc_id`
- `game_day`
- `plan_revision`
- `planner_version`
- `status / failure_reason`

### 8.2 Mutation 协议

mutation 使用独立 request/terminal，不复用旧 `NPC_SCHEDULE_REPLAN_REQUEST`，避免把“追加一个任务”伪装成“替换整日计划”。迟到、revision 冲突、非法 candidate、不可抢占和跨 segment 请求都返回稳定领域原因。

### 8.3 存档

Unity 主存档至少保存：

- day plan identity 与 fingerprint
- 当前 segment
- 两个剩余队列
- 已消费/退役 task ID
- 计划 revision

活动移动、动画 coroutine、社交 reservation 和 mutation in-flight 仍属于临时状态，不直接持久化。读档后由 Unity 取消临时 owner，并从保存的队列和 segment 恢复下一合法任务。

## 9. Test 时间档

Test 时间档目标改为现实 20 分钟一天：

```text
test_day_real_seconds = 1200
production_day_real_seconds = 1800
```

对应观察时间：

- 1 游戏小时约 50 秒。
- 08:00-17:00 工作段约 7.5 分钟。
- 17:00-24:00 休息段约 5.8 分钟。

若 `_flowProfile / _testDayRealSeconds` 是场景或 Prefab 上的 SerializeField，实施阶段必须先读取 `UnityMCPUsageRules.md` 并通过 Unity MCP 修改资产层；不得只改 C# 默认值掩盖已序列化配置。

## 10. 诊断要求

`aisc_debug` 应提供单 NPC `day_plan_snapshot`，至少包含：

- `game_day / plan_revision / planner_version`
- `active_segment`
- `active_task_id / phase / completion_policy / interrupt_policy`
- `work_remaining_count / rest_remaining_count`
- 最近 segment boundary 及退役计数
- 最近 mutation operation、来源、裁决和稳定原因
- 最近任务终态及来源

保留 owner trace 的候选分组、证据 ID、LLM/fallback 状态和耗时；删除对 `pending_candidate_id / planned_start_time / schedule_window_expired` 的生产诊断依赖。

## 11. 建议执行阶段

以下阶段用于后续正式 plan，不授权本轮直接实施。每一阶段完成自身最低门禁后才能进入下一阶段。

### 阶段 0：确认口径与创建实施 plan

1. 确认午夜仍活动工作任务的强制终态语义。
2. 确认玩家任务每次对话最多一个 mutation。
3. 确认默认 duration 使用 Gameplay 时间域及各 action 初始持续量。
4. 确认 `work_open / work_close` 迁移为 segment 生命周期动作。
5. 创建唯一 plan，列出旧协议退役顺序、测试工具和回滚边界。
6. 因现有 coordinator 会显著增重，实施前请求用户下达“减重”指令。

门禁：用户确认未决口径；plan 与现有日程、对话、午夜、协议 Workstream 互链。

### 阶段 1：共享领域契约与纯逻辑 seam

1. 定义 `NpcDayPlan / NpcPlanSegment / NpcPlannedTask / NpcTaskMutation`。
2. 在 task catalog 增加 segment、completion policy 和 interrupt policy 元数据。
3. 建立纯逻辑 `NpcDayPlanRuntime` seam 和状态转换测试。
4. 固定 17:00、午夜、失败、取消、抢占和跨日原子换代规则。

门禁：纯 C# EditMode 覆盖队列推进、边界退役、强制终态、抢占、迟到 mutation 和 revision 冲突；不得依赖场景对象。

### 阶段 2：后端两段式计划生成

1. 候选构建按 catalog 元数据分段。
2. Prompt 一次返回两个 candidate ID 队列，不输出时间和持续量。
3. 更新 parser、最终校验、deterministic fallback 和安全 trace。
4. 保持 5 名 NPC 有界并发和同日幂等。

门禁：Python 聚焦测试覆盖合法输出、跨段 candidate、重复 candidate、required 约束、provider timeout、fallback 和同日 fingerprint；完整计划不含 `HH:MM`。

### 阶段 3：Unity 队列执行与阶段边界

1. 将日程运行时职责迁入独立深模块，不继续扩张 `NpcSpawner` 或 `GameManager`。
2. 接入现有 `NpcTaskExecutor` 的移动、动作和终态。
3. 任务终态后自动取下一项；失败/取消不触发整表 replan。
4. 实现 17:00 工作收口、休息启动和午夜强制终态/退役。
5. 接入存读档、跨日换代和结构化诊断。

门禁：Unity EditMode 状态机全覆盖；PlayMode 隔离 probe 证明工作队列顺序执行、17:00 当前任务续跑、剩余工作退役、休息启动和午夜结算不悬挂。

### 阶段 4：对话与任务变更

1. 删除 NPC-NPC COMPLETE 后的整表 replan 生产入口。
2. NPC-NPC 对话只暂停/恢复任务或继续队列，摘要继续写记忆。
3. Player-NPC 对话增加结构化 mutation 输出与 Unity 接受/延后/拒绝终态。
4. 玩家抢占复用 `NpcDayPlanRuntime.ApplyMutation`，不得直接抢占 executor。
5. 为未来实时 LLM 保留同一 interface 和独立权限配置。

门禁：NPC-NPC 对话前后 plan revision 与队列不变；玩家 append/preempt/defer/reject 四条路径均有 operation、revision、终态和任务恢复证据。

### 阶段 5：旧时间点 replan 退役

1. 删除窗口错过触发的 `NPC_SCHEDULE_REPLAN_REQUEST` 生产入口。
2. 删除普通任务对 `planned_start_time / execution_window_* / miss_policy` 的运行时依赖。
3. 删除 NPC-NPC/普通玩家对话整表 replan context。
4. 迁移或删除 `NpcScheduleReplanTracker`，不得留下双 owner。
5. 更新协议兼容层、存档迁移、诊断和相关 README/Workstream。

门禁：静态搜索无旧生产消息、旧每分钟 replan、旧窗口裁决和双路径；兼容入口若保留必须无生产 caller。

### 阶段 6：20 分钟 Test 档与真实 PlayMode

1. 按 Unity MCP 资产规则把 Test 一天调整为 1200 秒。
2. 真实运行完整工作段和休息段。
3. 观察任务持续、移动、NPC-NPC 对话、玩家抢占和午夜结算。
4. 以结构化诊断取证，Console 只补异常。

门禁：完整 day 1 无 `schedule_window_expired / replan_already_in_flight / schedule_snapshot_version_mismatch`；队列和边界裁决可解释，午夜稳定进入 day 2。

### 阶段 7：独立测试与清零

1. 独立测试会话读取 plan 与 execution，按测试 Workstream 选择 Python、EditMode、PlayMode、`aisc_debug` 和 `aisc_control`。
2. 覆盖新游戏、同日读档、跨日、后端重启恢复、任务失败、边界退役、NPC-NPC 对话、玩家任务 mutation 和午夜。
3. 创建互链 test record；失败返回新的执行会话。
4. 通过后更新旧草案和 Workstream，明确哪些时间点日程口径已退役。

门禁：全部验收标准有结构化证据；未覆盖项不得因自动化通过而推定通过。

## 12. 预计影响范围

后端主要影响：

- `backend/src/npc/daily_schedule.py`
- `backend/src/npc/schedule_candidates.py`
- `backend/src/npc/schedule_validation.py`
- `backend/src/npc/schedule_prompt_adapter.py`
- `backend/src/npc/behavior_engine.py`
- NPC-NPC social complete 与 Player-NPC dialogue terminal 编排
- 对应 `backend/tests/`

Unity 主要影响：

- `NpcDailyScheduleModels.cs`
- `NpcDailyScheduleRuntimeCoordinator.cs`（职责迁移后减重或退役）
- 新的 `NpcDayPlanRuntime.cs`
- `NpcTaskExecutor.cs`
- `NpcBehaviorApplier.cs`
- 对话/social 协议适配
- 存读档与诊断 DTO
- 对应 EditMode / PlayMode probe

资产影响：

- `GameTimeController` 的 Test 时间档 SerializeField 所在场景或 Prefab；必须通过 Unity MCP 修改。

## 13. 验收标准

1. 每名 NPC 每日一次 LLM 返回两个有序队列，普通任务不含精确时间。
2. Unity 只在当前任务终态后启动下一任务，不再每分钟判断普通任务是否错过。
3. 17:00 时当前工作可继续，剩余工作稳定退役；终态后进入休息队列。
4. 午夜时当前休息任务强制终态、剩余休息任务退役，午夜结算不悬挂。
5. NPC-NPC 对话不改变 plan revision、队列内容或触发整表 replan。
6. Player-NPC 对话只有在存在合法玩家安排时产生至多一个 mutation；append、preempt、defer 和 reject 均可诊断。
7. 任务失败或取消消费当前任务并继续，不触发 revision 循环。
8. Test 一天现实 20 分钟；完整 PlayMode 日内无窗口错过 replan 相关错误。
9. `work_open / work_close` 由工作 segment 生命周期确定性执行，不依赖 LLM 队列位置。
10. 存读档和跨日不会恢复旧活动 owner、旧 mutation pending 或错误 segment。

## 14. 风险与停止条件

1. 若任务 catalog 无法稳定声明 segment、完成和抢占策略，停止后端/Unity 接入，先补共享领域契约；不得在两端分别猜测。
2. 若当前活动工作任务跨午夜没有明确终态，停止午夜集成；不得允许日终永久等待。
3. 若 Player-NPC 对话需要自由生成未实现玩法，稳定拒绝并保留对话语义，不把自由文本直接执行为任务。
4. 若 `NpcDailyScheduleRuntimeCoordinator`、`NpcTaskExecutor` 或 `GameManager` 会继续显著增重，必须先获得用户“减重”指令并拆出深模块。
5. 若 Test 时间配置涉及场景、Prefab 或 SerializeField，Unity MCP 不可用时停止资产修改并请求用户指示。
6. 若迁移期间出现旧日程和新队列双 owner，停止继续扩展，先完成单 owner 收口。
7. 若取消精确时间破坏营业、约会或剧情硬时点，相关事件应提升为 segment lifecycle 或独立世界事件，不能重新把所有普通任务塞回时间点日程。

## 15. 与现有文档的关系

1. `ContextAwareDailyScheduleDraft.md` 的候选、记忆证据、物理过滤、单次 LLM 和诊断原则继续有效；精确时间点、傍晚社交时间窗和互动后整表 replan 部分在本草案采纳后退役。
2. `DailySchedulePlayModeFindingsDraft.md` 保留历史复现与证据，不改写既有失败结论。
3. `NpcBehavior/README.md` 与 `Dialogue/README.md` 当前仍描述已上线的旧整表 replan；只有实施和独立测试通过后才能更新为本草案口径。
4. 后端重连与 `blocking_message` 仍属于 ProtocolAndSave 独立问题，不因队列重构自动解决。

## 16. 待确认项

1. 活动工作任务异常跨到午夜时，建议统一强制终态并进入结算；是否接受该口径。
2. 玩家一次对话最多产生一个 mutation；是否接受该上限。
3. `work_open / work_close` 迁移为 segment enter/exit 生命周期动作；是否接受不再由 LLM 选择。
4. 默认 duration 使用 Gameplay 时间域；各 action 初始持续量在实施 plan 中按 task catalog 明确。
5. 玩家抢占后旧任务默认退役，不自动回队；需要恢复的任务必须由 interrupt policy 显式声明。
