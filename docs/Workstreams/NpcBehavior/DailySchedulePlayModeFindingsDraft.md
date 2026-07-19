# NPC 日程 PlayMode 验收问题草案

## 定位

本文件记录 2026-07-19 真实 PlayMode 日程验收中发现的问题，只承担复现、证据和后续设计边界，不是 implementation plan，不授权直接修改运行代码。

## 问题一：新游戏回放上一局同日持久化日程

### 复现

1. 完成一轮 day 1 新游戏，使 Python 写入 `npc_daily_schedule_snapshots`。
2. 退出 Play Mode，保持同一后端数据库。
3. 再次进入 Play Mode并点击新游戏。

### 证据

1. 协议完成新的 `hello / hello_ack`、`world_snapshot / world_snapshot_applied`。
2. 新游戏完成 `memory_checkpoints_purge_all / memory_checkpoints_purged_all`。
3. 返回的日程仍具有上一局完全相同的 `daily_schedule_v1`、operation ID、candidate ID 和 payload fingerprint。
4. 新后端进程内没有对应 trace，因此 `backend_owner_trace=null`。
5. `MemoryCheckpointService.purge_all()` 只清记忆检查点；`npc_daily_schedule_snapshots` 没有新游戏清理入口。

### 期望

新游戏必须隔离上一局所有按 game day 幂等的 Python 运行持久化数据；同一局重连仍应复用快照，不能用“新游戏一律不幂等”破坏重连语义。

## 问题二：运行时 replan 缺冻结快照契约并循环重发

### 复现

1. 运行旧 day 1 日程直到 required 候选窗口过期。
2. Unity 触发 `NPC_SCHEDULE_REPLAN_REQUEST`。

### 证据

1. Unity 请求携带 `world_revision` 和降级 `physical_state`，但没有 `snapshot_id / time_revision`。
2. 后端存在 `snapshot_store` 时强制执行 `snapshot_store.require("", -1, world_revision)`，在 planner 前抛出 `ValueError`。
3. Unity `RequestReplan` 不检查 `_replanOperationByNpc` 是否已有 pending，每个游戏分钟生成新 operation ID。
4. Console 连续出现 `schedule_replan_rejected:ValueError`；`kujo` 长期保持 `last_replan_status=pending`，没有 backend owner trace。
5. 运行时 replan 错误覆盖了已经完成的 `world_preparation.failure_reason`，造成跨 operation 状态污染。

### 期望

1. replan 必须携带并校验与当前 Unity 权威世界一致的冻结 snapshot ID、time revision 和 world revision，或使用明确设计的等价正式 seam。
2. 每名 NPC 同一 base schedule revision 最多一个 in-flight replan；响应、稳定拒绝、超时或显式取消后才能再次申请。
3. 失败必须终态化 pending，并提供稳定失败码，不得只暴露异常类型 `ValueError`。
4. 运行时 replan 诊断不得写入 world preparation operation 的 failure reason。

## 相关问题

运行中后端重启被立即升级为致命退出，见 `docs/Workstreams/ProtocolAndSave/BackendReconnectFatalDraft.md`。

## 问题三：跨日新计划与旧 revision/pending 状态发生竞态

### 复现

1. day 1 已持有 revision 1 日程，其中部分 NPC 存在旧 pending replan。
2. 通过 `aisc_control.run_midnight_settlement` 执行正式午夜流程。
3. 午夜维护成功后进入 day 2 世界准备。

### 证据

1. `aisc_debug.midnight_snapshot` 返回 `status=success`、`phase=complete`，5 名 NPC 印象刷新全部成功，总耗时约 11.63 秒。
2. Unity 已切换到 day 2 06:00、雨天，但 `daily_schedule_snapshot` 仍保留 day 1 revision 1。
3. day 2 新计划同样从 revision 1 开始；`TryReplace` 在旧日状态尚未由 Tick 清理时将其拒绝为 `revision_content_conflict`。
4. chihaya、kazuha 还保留 day 1 pending replan operation，导致 day 2 正常批次结果被拒绝为 `operation` 不匹配。
5. `world_preparation` 停在 `entering_world`，说明午夜成功不等于次日世界成功。

### 期望

1. 接收不同 `game_day` 的正式计划时必须先原子终态化旧日任务、pending replan 和 revision，再按新日契约接收，不能依赖之后才运行的分钟 Tick 清理。
2. schedule revision 的比较必须明确作用域是全局还是 `(game_day, npc_id)`；若按日重置为 1，内容冲突判断必须包含 game day。
3. day 1 pending operation 不得阻止 day 2 完整计划。
4. 次日计划被拒绝时 world preparation 必须以稳定失败码终态化，不能停留在 `entering_world`。

## 诊断钩子验收补充

1. 六个隔离日程探针已全部通过。
2. provider timeout 真实探针发现 Python 64 位 fallback seed 与 Unity Int32 DTO 不一致，已把诊断字段改为 `long` 并补回归。
3. 空 replan operation 曾错误吸附同 NPC 的无关 trace，已改为明确 operation 前缀关联。
4. fallback reasons 已限制为最多 50 条，避免 295 个候选放大诊断载荷。
5. 无有效内容的 Sakura 对话立即取消后，revision 保持 1 且没有 replan operation，取消语义通过。

## 问题四：真实 planner 输出全部进入 fallback

### 隔离条件

清空 `npc_daily_schedule_snapshots` 并重启实际监听 8766 端口的 Python 进程后，重新执行正式新游戏。5 名 NPC 均生成 `daily_schedule_v2`，owner trace 与当前 operation 正确关联。

### 真实结果

1. sakura、chihaya、tatsunosuke：`planner_rejected:ValueError / required_candidate_missing`。
2. kazuha：`planner_rejected:AttributeError / 'str' object has no attribute 'get'`。
3. kujo：`planner_rejected:ValueError / non_monotonic_schedule`。
4. 每名 NPC 候选数约 293–301，fallback 最终选择 8 项；candidate group 包含大量 exploration/relationship 候选。
5. fallback 本身能稳定收口，但真实 LLM 路径 5/5 未通过最终校验。

### 初步边界

1. `required_candidate_missing` 需要核对 required 候选数量是否可能超过输出 6–10 项上限；若超过，候选分级与输出契约本身不可同时满足，不能只靠 Prompt 要求供应商修正。
2. `parse_selection` 对数组元素没有先验证 object/dict，供应商返回字符串元素时泄漏 `AttributeError`；应收口为稳定 `schedule_item_not_object` 等领域错误。
3. `non_monotonic_schedule` 说明受控 JSON 仍需明确排序/去重纠正策略；是否整体 fallback 保持不变需在后续方案中决定。
4. `failure_detail` 已证明可区分真实拒绝分支，但正式稳定失败码仍不能仅依赖 Python 异常文本。

## 真实 NPC 社交长链补充

1. 固定 `sakura/chihaya` 分别从 `street.arcade/street.vending_machine` 通过真实移动会合到 `street.crossroad`，正式内容与播放链终态为 `completed`，world revision 为 2。
2. 会合启动后立即调用正式玩家对话入口，社交终态为 `player_dialogue_interrupted`；玩家对话进入活动态，dialogue pause 正常生效，双方社交 reservation 已释放。
3. 会合启动后用第二个真实移动命令取消 Sakura 的会合移动，双方移动终态收口为 `movement_failed`，reservation 已释放，未进入内容播放。
4. 三条链使用 `current_play_session_only` 白名单钩子，不写正式配置或存档；它们验证 post-decision 的 Unity 权威会合/抢占/终态链，不替代自然候选与语义 decision 的随机触发验证。
5. 该 probe request 的 `aisc_debug.protocol_trace` 为空，说明当前协议 trace 未覆盖这类从 post-decision seam 发出的社交 content/failed/complete 消息，后续需要补齐或明确不适用原因。
6. 玩家抢占后既有 replan 问题继续每分钟产生 `schedule_replan_rejected:ValueError`，并写入已完成的 `world_preparation.failure_reason`；与上文问题二一致，不是社交 reservation 失败。
7. 因 PlayMode probe 绕过后端 decision pending，玩家抢占发出的 FAILED 被后端以空 reason 拒绝；这是探针边界，同时暴露拒绝诊断缺少稳定 reason，不能据此判定自然 decision 链失败。

## 后续验收门槛

1. 新游戏生成当前 planner version 的全新 day 1 日程；同局重连才允许幂等回放。
2. 固定输入、provider timeout、17:00、社交锁、任务失败和迟到 revision 白名单探针全部通过。
3. 真实 required 窗口过期只产生一个 operation，并能从 pending 收口到 accepted 或稳定 failed。
4. `interaction_replan_snapshot` 能关联 Unity operation 与 backend owner trace。
5. Console 无每分钟重复的 replan 错误。
