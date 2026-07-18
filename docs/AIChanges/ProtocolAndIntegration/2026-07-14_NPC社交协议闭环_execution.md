# NPC-NPC 社交协议闭环执行记录

> 设计方案: [plan.md](2026-07-14_NPC社交协议闭环_plan.md)

## 实际改动

### 后端

1. 新增 `NpcSocialSessionCoordinator`，管理 PREPARE、READY、FAILED、COMPLETE、会合超时和播放超时。
2. `BehaviorEngine` 不再在准备后立即发送旧 `NPC_SOCIAL_ACTION` 或立刻重新规划。
3. Unity READY 后才调用 LLM；气泡携带 `request_id`、`line_index` 和 `line_count`。
4. Unity COMPLETE 后才写短期记忆和双方即时印象。
5. FAILED、超时、断线或空内容均不写入对话记忆，并在终态后恢复双方计划。

### Unity

1. 新增 `NpcSocialProtocolController`，同时移动双方并使用真实 `MovementResult` 判断会合成功或失败。
2. 会合 deadline 使用后端下发值，默认和上限为 120 秒；使用 realtime 计时，不受游戏暂停影响。
3. 新协议气泡不再进入旧 12 秒等待逻辑。
4. 最后一句气泡显示完成后回报 COMPLETE。
5. 玩家正式对话可抢占准备中或播放中的 NPC-NPC 会话，并回报 FAILED。
6. 后端 CANCEL 会清理队列和锁，不产生迟到终态。

### Unity 资产

通过 Unity MCP 将 `Town_Main` 中活动和 legacy `NpcBubbleManager` 的兼容 `_npcDialogueWaitTimeoutSec` 从 12 秒调整为 120 秒，并保存场景。

## 验证

1. `python -m unittest discover -s backend/tests -q`: 31 项通过。
2. `python -m compileall -q backend/src backend/tests`: 通过。
3. `python backend/scripts/check_project_conventions.py`: 通过。
4. Unity MCP 全量刷新与编译：Console 0 error。
5. 后端当前未运行，未完成真实双进程 Play 验证。

## 未完成项

1. Play 模式观察跨店会合、移动失败、玩家抢占和完整轮播。
2. 当前会合目标仍是同一 `location_id` 的位置点；更自然的面对面双站位依赖后续 social spot / anchor 细化。

## 当前口径去污染回写

1. 更新 `CodebaseBigPicture.md` 的 NPC-NPC 社交时序图和职责边界。
2. 更新 `ProtocolAndSaveFoundation.md`，写入 READY/FAILED/COMPLETE、120 秒监督和记忆提交规则。
3. 更新 Unity Dialogue、Python NPC/API 目录 README 与三个相关 Workstream。
4. 在最相关的旧 plan / execution 顶部增加历史状态提示，保留原文但明确不再代表当前实现。
5. 回写 DesignDocs 索引和 Roadmap，避免后续 AI 从旧 `NPC_SOCIAL_ACTION -> NPC_BUBBLE` 链继续扩展。
