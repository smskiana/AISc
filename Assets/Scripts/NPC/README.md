# NPC 脚本目录

## 文件夹功能

保存 Unity 侧 NPC 实体、生成、查找和行为表现代码。

## 文件夹内容

包括 NPC 状态应用、移动呈现、空闲表现、名字牌、对话气泡和社交会合。后端行为决策位于 `backend/src/npc/`。

## 核心入口

- `NpcBehaviorApplier.cs`: 行为协议消息的薄适配层。
- `NpcTaskExecutor.cs`: 正式任务的移动、动作阶段、终态和状态询问响应。
- `NpcEntity.cs`: NPC 实体状态、walk/run 移动入口和动作表现。
- `NpcAmbientBehaviorController.cs`: 不回写后端的可抢占空闲表现。

`NpcTaskExecutor` 可导出活动任务和最近终态的只读诊断快照，并通过 `aisc_debug` 的 `npc_task_snapshot` action 提供给 AI 调试流程。

`NpcDailyScheduleController` 是 Unity 已接收剩余日程的权威托管器；`NpcSpawner` 会在 Unity 主存档中保存并恢复同游戏日的剩余项。`aisc_debug` 的 `daily_schedule_snapshot` 可读取 revision、pending candidate 和最近裁决，不包含模型原文或临时 in-flight。

`NpcDailyScheduleRuntimeCoordinator` 负责接收、分钟裁决、17:00 压缩、任务终态消费、跨日原子换代和日程存读档；`NpcScheduleReplanTracker` 独立负责 replan 单飞、冻结快照引用、匹配终态、135 秒超时与跨日取消，`NpcSpawner` 只保留生命周期接线。任务 started/moving/performing/terminal 均携带 candidate 与 schedule revision 进入 `NPC_RUNTIME_EVENT`。

`NpcDayPlanRuntime` 是两段式任务队列的唯一生产 owner，持有 plan revision、work/rest 队列、活动任务、17:00/午夜边界和有界 mutation；`NpcDailyScheduleRuntimeCoordinator` 只适配协议/生命周期并通过唯一 seam 驱动 `NpcTaskExecutor`。旧分钟 controller/replan tracker 仅是无生产 caller 的迁移壳。

`NpcSocialCandidateController` 是纯运行时社交候选扫描器：它只向 Python 发送已经满足物理条件的候选，并在意愿结果返回后重新校验物理事实；会合、锁和冷却仍由 Unity 承担。

`NpcSocialProtocolController` 是 Unity 权威社交 session owner：独立持有双方 reservation、会合、内容等待、播放、超时、失败原因和终态释放。`aisc_debug` 的 `npc_social_snapshot` 可读取活动阶段和最近终态。
