# NPC 日程诊断验收与协议清零执行记录

> 设计方案: [2026-07-18_NPC日程诊断验收与协议清零_plan.md](2026-07-18_NPC日程诊断验收与协议清零_plan.md)

## 实际改动

1. 扩展 `aisc_debug.daily_schedule_snapshot`，把 Unity revision、pending、17:00 压缩、最近裁决与后端 owner trace 关联；新增 `interaction_replan_snapshot`。
2. 后端 owner trace 增加候选分组计数、证据 ID、执行阶段、校验状态、fallback seed/reason、耗时和稳定失败原因；不包含 Prompt、模型原文或 embedding。
3. 新增 `aisc_control.run_daily_schedule_probe` 六个白名单场景：`fixed_input_planner`、`provider_timeout`、`jump_to_17`、`social_lock_defer`、`task_failure_replan`、`late_revision`。全部调用正式 planner/controller seam，写入范围固定为 `isolated_in_memory_only`。
4. 增加 Python 与 Unity EditMode 回归测试，并修正 FrontendArchitecture、NpcBehavior、Navigation、ProtocolAndSave、Dialogue 和 Diagnostics 当前入口口径。
5. 全仓生产代码审计未发现 `NPC_BEHAVIOR`、`NPC_TASK_STATUS*`、`NPC_ACTION_RESULT*`、旧时间控制和旧 wake/sleep push 引用；没有外部消费者可迁移，因此本轮无需删除仍被调用的 DTO。
6. 新增 `aisc_control.run_npc_social_probe` 四个白名单隔离场景：`complete`、`player_preempt`、`rendezvous_failure`、`late_content_revision`。探针复用 `NpcSocialProtocolController` 的 reservation、移动终态、内容接收、播放完成和按 NPC 取消状态转移，不替换真实 `ActiveInstance`。

## 验证证据

1. 快速 Python 环：6/6，通过，0.13 秒；修正探针后专项 6/6，通过，0.09 秒。
2. Python 全量：68/68，通过，17.43 秒。
3. Unity EditMode 全量：34/34，通过，0.88 秒；日程/诊断专项曾单独 23/23，通过，0.44 秒。
4. Unity 编译与 Console：刷新编译完成，0 error。
5. Unity 白名单控制探针实际调用：`jump_to_17=Switch`、`social_lock_defer=Defer`、`task_failure_replan=RequestReplan`、`late_revision=rejected/stale_schedule_revision`，均声明 `isolated_in_memory_only`。
6. Unity PlayMode 测试框架可启动，但项目当前返回 0 个 PlayMode 用例，不能作为长链证据。
7. 实际进入 `Town_Main` 后，`aisc_debug.health_report` 返回 `websocket_disconnected` 与 `gameplay_not_ready`；`daily_schedule_snapshot` / `interaction_replan_snapshot` 因未建立游戏会话为空。
8. codebase-memory full 重建首次因 worker 单文件崩溃失败；按工具建议重试 moderate 成功，持久化结果为 11060 nodes / 25086 edges，并同步更新时间文档。
9. 真实 `provider_timeout` 探针先发现 Python fallback seed 与 Unity Int32 DTO 不一致；扩大为 `long` 后，真实新游戏又出现接近/超过有符号 Int64 的无符号哈希 seed，最终改为十进制字符串跨端传输并补 UInt64 最大值回归。
10. 真实取消对话取证发现空 replan operation 会误关联同 NPC 的其他 trace，且大候选 fallback reasons 无界；已改为按明确 operation 前缀关联，并把 reasons 限制为 50 条。
11. 真实 `daily_schedule_v2` 生成全部 owner 进入 `ValueError/AttributeError` fallback；为继续隔离拒绝原因，owner trace 新增最多 200 字符、无 Prompt/模型原文的 `failure_detail`。
12. NPC 社交专项 EditMode 4/4 通过；Unity EditMode 全量更新为 40/40，通过，0.95 秒。
13. 通过 Unity MCP 实际调用四个 `run_npc_social_probe` 场景，均返回 `success=true`、`both_reserved_initially=true`、`both_released=true` 和 `write_scope=isolated_in_memory_only`。正常完成终态为 `completed`，玩家抢占为 `player_dialogue_preempted`，移动失败为 `movement_failed`，终态后的迟到内容被拒绝。
14. 新增 `aisc_control.start_npc_social_playmode_probe`，固定 `sakura/chihaya` 从 `street.arcade/street.vending_machine` 向 `street.crossroad` 会合，写入范围为 `current_play_session_only`；它调用正式社交协议、真实 NPC A* 移动、后端内容和玩家对话入口，不接受任意方法或任意对象反射。
15. 三条真实 PlayMode 社交长链通过：`cross_location_complete` 由 `rendezvous` 进入内容/播放并终态 `completed`（world revision 2）；`player_preempt` 进入正式玩家对话、暂停游戏并以 `player_dialogue_interrupted` 终态；`rendezvous_failure` 由第二个真实移动命令取消会合移动并以 `movement_failed` 终态。三条链后均可重新 reservation，证明双方释放成功。

## 未完成项

1. 计划列出的 CONTINUE、同日重连、旧档、真实供应商 120 秒、社交超时和断线等 PlayMode 长链仍未全部获得真实运行证据；真实 NPC 跨位置完成、玩家现场抢占和移动取消失败已通过。
2. 按计划停止条件，不以 EditMode/单元测试替代上述长链结论；本方案保持部分完成，原总方案不得标记完成。
3. 后端两项 planner 探针已由 Python 自动测试验证，但本次 Play 会话后端未连接，未通过 Unity `aisc_control` 现场调用 HTTP 入口。

## 问题与防复发

探针夹具曾因 revision 0 和猜测 candidate ID 命中错误拒绝层，已修正并记录到 `docs/DesignDocs/errors/2026-07-19_schedule_probe_fixture_contract.md`。

真实社交 PlayMode 取证同时确认两项未收口诊断问题：直接从正式 post-decision seam 启动的 probe request 在 `protocol_trace` 中为空；玩家抢占后既有运行时 replan 仍循环返回 `schedule_replan_rejected:ValueError` 并污染 `world_preparation.failure_reason`。后者已在 `DailySchedulePlayModeFindingsDraft.md` 记录，不能归因于社交 reservation/会合状态机。
