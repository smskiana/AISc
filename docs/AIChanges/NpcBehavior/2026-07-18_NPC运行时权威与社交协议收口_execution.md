# NPC 运行时权威与社交协议收口执行记录

> 设计方案: [2026-07-18_NPC运行时权威与社交协议收口_plan.md](2026-07-18_NPC运行时权威与社交协议收口_plan.md)

## 可行性结论

方案可在既有职责边界内实施：候选、session/reservation、会合和气泡播放保持独立，没有继续向过重类堆状态。`PlayerDialogueService`、`WorldPreparationCoordinator`、午夜维护和 `BehaviorEngine` 改为接收 operation 冻结时间，职责是移除全局可写时钟依赖而非增加新状态，因此未触发类减重停止条件。

## 已完成修改

1. `NPC_SOCIAL_DECISION_RESULT` 只返回语义意愿，后端不再创建 session 或发送 PREPARE。
2. 新增 `NPC_SOCIAL_CONTENT_REQUEST / NPC_SOCIAL_CONTENT_RESULT`；Python 只生成结构化 lines，并按 request ID 幂等缓存。
3. Unity 成为 reservation、会合、内容等待、播放、超时、失败和终态释放的 owner；日程切换会尊重社交 reservation，播放阶段才使用 motion lock。
4. 删除后端 PREPARE/CANCEL/READY 监督与 asyncio 超时 task；只有匹配参与者且 revision 不陈旧的 COMPLETE 才提交记忆和 effect。
5. Unity 网络路由删除 `NPC_BEHAVIOR`、`WAKE_UP`、`GAME_TIME_UPDATE`、`SLEEP_TRIGGER` 和 `NPC_ACTION_RESULT_ACK`；内部任务改用 `NpcTaskCommand`，终态只发送 `NPC_RUNTIME_EVENT`。
6. 后端删除旧 `NPC_ACTION_RESULT / NPC_TASK_STATUS` 拒绝 ACK 分支，并删除 `StateManager.apply_tick()`。
7. 新增 `aisc_debug.npc_social_snapshot`，显示 reservation 后的会合、内容、播放阶段以及最近稳定终态原因。
8. `GAME_START` 和 `DIALOGUE_START` 携带 Unity 权威 `game_time / world_revision`；日计划、玩家对话、世界准备和午夜维护全程使用冻结 `GameTimeSnapshot`。后端业务层已清零 `game_clock`，仅 `main.py` 健康诊断保留只读缓存。
9. 后端旧 SAVE/LOAD/GET_SAVES 路由删除；Unity 同名旧命令方法保留 API 但只输出迁移警告，不再发送协议。

## 验证

1. Python 全量测试：`python -m unittest discover -s backend/tests -p "test_*.py"`，62 项通过。
2. Unity MCP 脚本刷新后无 C# 编译错误。
3. Unity EditMode：28 项通过，0 失败；新增双方 reservation 原子失败和迟到 request 不得释放新占用测试。
4. 全仓搜索确认正式代码不存在 `NPC_SOCIAL_PREPARE / NPC_SOCIAL_CANCEL / NPC_SOCIAL_READY`、网络 `NPC_BEHAVIOR`、`NPC_ACTION_RESULT`、`NPC_TASK_STATUS` 和 `StateManager.apply_tick()`。

## 未完成项与风险

1. 尚未完成真实 Play Mode 的移动失败、玩家抢占、内容迟到、断线和存读档冷却长链验证；现有 `aisc_control` 无法稳定构造任意 NPC pair 和导航失败条件。
2. 最终 Unity 刷新 Console 为 0 error；此前一次无文件路径的 `Import Error Code:(4)` 未复现。

## 诊断/控制钩子说明

本轮新增只读 `npc_social_snapshot`。未新增 `aisc_control` action，因为现有 `start_new_game` 与玩家对话控制不足以稳定构造任意 NPC pair 的物理位置和移动失败；专项 Play 长链仍作为剩余验证风险记录，不影响协议和权威边界源码收口结论。
