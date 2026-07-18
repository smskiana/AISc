> 设计方案: [plan.md](2026-07-17_开局与午夜世界准备加载门_plan.md)

# 开局与午夜世界准备加载门执行记录

## 实际改动

1. 新增 `backend/src/application/world_preparation.py`，以 `WorldPreparationCoordinator` 统一新游戏和跨日的阶段、操作 ID、稳定失败原因、串行执行与次日重复请求幂等。
2. `GameRuntime` 改为通过协调器延后 `GAME_READY` 与 `MIDNIGHT_SETTLEMENT_COMPLETE`；新增 `WORLD_PREPARATION_PROGRESS`，成功终态携带 `operation_id`，失败不再暴露原始异常详情。
3. `BehaviorEngine.ensure_daily_plans(game_day, ...)` 收敛指定日期日计划准备；新游戏清空旧世界幂等缓存，日计划 LLM 调用改为 `asyncio.to_thread`，不会阻塞协议事件循环。
4. Unity 接收准备进度，开始新游戏时立刻标记 `GameStateStore` not-ready 并申请既有 `LoadingOverlay` 暂停来源；`GAME_READY` 后才播放完成收口并释放遮罩。午夜继续由 `SleepFlow` 保持到自动存档 / 醒来流程完成。
5. `SystemMessageView` 扩展为资产化加载标题、阶段文本和 Slider 的假进度接口；未成功前上限为 95%，以 UI 时间域平滑。通过 Unity MCP 在 `Town_Main` 的既有 `pnl_loadingOverlay_dy` 下创建 `txt_loadingTitle_dy`、`sld_loadingProgress_dy`，完成 SerializeField 连线并绑定 `Assets/Fonts/MSYH SDF.asset`。
6. `aisc_debug.runtime_snapshot` 的 `world_preparation` 现包含操作 ID、flow、phase、活跃状态、进度下限、失败原因和目标游戏日；`aisc_control.start_new_game` 继续作为正式验证入口。
7. 修正加载阶段重复调用时重置 Slider 的问题：后续阶段只提高目标值，完成阶段等待视觉值实际收口到 100%。

## 文档回写

- 更新 FrontendArchitecture、NpcBehavior、ProtocolAndSave 工作流口径。
- 更新 Application、SystemMessages 和 Diagnostics 入口文档。

## 验证

1. `python -m unittest backend.tests.test_world_preparation backend.tests.test_pause_sync backend.tests.test_protocol_execution_loop`：21 项通过。
2. Unity MCP 刷新、编译完成，Console `error` 为 0。
3. Play 模式中调用 `aisc_control.start_new_game` 后，`aisc_debug.runtime_snapshot` 确认：`gameplay_ready=false`、`loading_overlay` 在 Gameplay 暂停来源中，且存在活跃的 `world_prepare_*` 操作、`initial_world / initial_memory` 阶段。
4. Unity EditMode `SystemMessageLoadingProgressTests.LaterLoadingStageDoesNotResetVisualProgress`：1 项通过。

## 未完成项 / 风险

1. 本轮 Play 验证已覆盖“立即锁定和阶段可观测”；完整 LLM 日计划完成与午夜自动存档闭环仍受本机供应商调用时长影响，需在可用 LLM 配额下再跑一次完整闭环。
2. 编辑器控制钩子按方案保持白名单，不新增任意阶段跳过或任意状态写入入口。
