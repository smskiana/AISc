# Unity 日程执行压缩与重规划收口执行记录

> 设计方案: [2026-07-18_Unity日程执行压缩与重规划收口_plan.md](2026-07-18_Unity日程执行压缩与重规划收口_plan.md)

## 实际改动

1. 新增 `NpcDailyScheduleRuntimeCoordinator`，从 `NpcSpawner` 拆出日程接收、分钟裁决、任务启动、终态消费、恢复重规划和同日剩余计划存读档职责。
2. 日程候选使用内部 `NpcTaskCommand`，携带 `candidate_id`、`schedule_revision`、来源和 `miss_policy`，不再依赖旧后端分钟行为消息。
3. `NpcTaskExecutor` 在替换活动任务前先回报 `cancelled + schedule_preempted`；started、moving、performing 与 terminal 均通过 `NPC_RUNTIME_EVENT` 携带 candidate 和 revision。
4. 失败和取消不再作为成功消费；required 的 `request_replan` 走独立 `runtime_recovery` eligibility，普通可跳过项显式消费。
5. 17:00 压缩只处理 remaining：按 required、important、optional 排序，删除已过窗口的非必需项，保留过期 required 进入显式恢复裁决，不调用 LLM。
6. 重规划结果按 operation ID、日和 schedule revision 拒绝迟到或冲突结果；请求只携带受影响 NPC 的权威 remaining 与 base revision。
7. 存档仅写当前游戏日未终态消费的 remaining；恢复只接受同日且 revision 有效的计划。职责迁移时原有 runtime need/asleep/concern 存档语义保持不变。
8. `daily_schedule_snapshot` 增加压缩前后计数、压缩状态、最近裁决和重规划 pending 状态。

## 文档与诊断同步

- 更新 NPC Workstream 与 `Assets/Scripts/NPC/README.md`，记录 coordinator、运行时事件和压缩口径。
- `aisc_debug.daily_schedule_snapshot` 调用成功；编辑态无活动日程时返回空数组，入口可用。

## 验证

- codebase-memory moderate 重建：11001 nodes / 24845 edges。
- Python：`test_daily_schedule_planner.py` 与 `test_protocol_execution_loop.py` 共 14 项通过。
- Unity EditMode：`NpcDailyScheduleTests` 5 项通过，覆盖 revision 冲突、锁 defer/窗口恢复、旧档迁移和压缩优先级/过期项。
- Unity Console：脚本刷新编译后 0 error。
- Unity PlayMode：当前项目发现 0 个 PlayMode 测试；因此长任务、社交锁、玩家抢占、17:00 跳时、午夜和真实存读档长链没有自动化证据，转入后续“NPC 日程诊断验收与协议清零”执行案，不在本记录中伪报通过。

## 未完成项

本 plan 的运行时代码与 EditMode 验收已完成。真实场景 PlayMode 长链仍由下一阶段专项验收；当前 miss policy 契约只有 `skip_next` 与 `request_replan`，没有可执行的替代 spot DTO，因此替代 spot 继续属于 Workstream 已记录的 affordance 恢复策略，不在本轮虚构运行时 fallback。
