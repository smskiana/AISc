# Unity 日程执行压缩与重规划收口执行方案

> 执行记录: [2026-07-18_Unity日程执行压缩与重规划收口_execution.md](2026-07-18_Unity日程执行压缩与重规划收口_execution.md)

## 1. 目标与边界

完成 Unity 对剩余计划、切换、消费、抢占、17:00 压缩、失败恢复和互动后局部重规划的运行时权威。本阶段使用上一阶段产出的已验证计划，不修改后端候选评分算法。

## 2. 实施步骤

1. 将计划任务输入与旧 `NpcBehaviorMsg` 解耦，建立 Unity 内部任务命令，携带 candidate、schedule revision、来源和 miss policy。
2. 切换采用统一裁决 seam；日程、P0/need 和 brain 意图都必须通过该 seam，不能直接覆盖活动任务。
3. `switch` 必须先把可抢占旧任务终态化为 `cancelled + schedule_preempted`，再启动新任务；自然终态不重复取消。
4. 按 succeeded、failed、cancelled、defer、skip 分别处理计划项；失败/取消不能伪装成功，并按 miss policy 选择替代 spot、skip 或 replan。
5. `NPC_RUNTIME_EVENT` 补齐 started/phase/terminal，以及 event/world/request/candidate/schedule/npc/action/origin/target/actual/target person/movement/result 字段。
6. 在 17:00 附近增加一次本地压缩：仅处理未开始项，required → important → optional，重新校验时间、窗口、归属和世界条件，不增加 LLM 调用。
7. 互动重规划只发送受影响 NPC 的权威剩余计划和 base revision；后端返回结果必须与 request、day、base revision 对应，迟到结果拒绝。
8. 修正非互动 `request_replan` 的 eligibility：窗口错过、执行失败与互动完成使用不同触发类型和后端入口，不伪装成 completed interaction。
9. 存档只保存当前日未终态消费的剩余计划；旧 schema、跨日和不同日读档必须显式请求当前日计划，不依赖偶然广播。

## 3. 预计涉及文件

- `Assets/Scripts/NPC/NpcDailyScheduleController.cs`
- `Assets/Scripts/NPC/NpcDailyScheduleModels.cs`
- `Assets/Scripts/NPC/NpcSpawner.cs`
- `Assets/Scripts/NPC/NpcTaskExecutor.cs`
- `Assets/Scripts/NPC/NpcBehaviorApplier.cs`
- `Assets/Scripts/Core/GameCommandSender.cs`
- `Assets/Scripts/Save/GameSaveData.cs`
- `backend/src/application/runtime.py`
- `backend/src/npc/behavior_engine.py`
- `backend/src/npc/daily_schedule.py`
- 相关测试

如果 `NpcSpawner` 需要继续增加压缩、恢复、协议和任务状态分支，必须停止并请求类减重指令，优先拆出日程 runtime coordinator。

## 4. 诊断与验证

1. EditMode 覆盖 switch 原子顺序、锁 defer、窗口过期、失败恢复、迟到 revision 和压缩稳定性。
2. PlayMode 覆盖长任务跨计划点、NPC-NPC 锁、玩家抢占、存读档、跳到 17:00、午夜和旧档迁移。
3. `aisc_debug.daily_schedule_snapshot` 显示当前任务关联、pending、压缩前后、最后裁决和 replan request/result。
4. 后端只幂等接收 runtime event，不查询、重发、监督或据此启动任务。

## 5. 验收标准

- Unity 独立托管日程运行，不依赖后端分钟指令。
- 抢占、完成、失败、取消、延迟和跳过具有不同稳定语义。
- 17:00 压缩不调用 LLM，不重写已开始或已完成项目。
- 互动与非互动重规划均使用正确 eligibility 和剩余计划。

