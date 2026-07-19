# NPC 日程 PlayMode 缺口收口执行记录

> 执行方案：[2026-07-19_NPC日程PlayMode缺口收口_plan.md](2026-07-19_NPC日程PlayMode缺口收口_plan.md)
>
> 待独立测试：[2026-07-19_NPC日程PlayMode缺口收口_test.md](2026-07-19_NPC日程PlayMode缺口收口_test.md)

## 执行结论

实现完成，待独立测试。当前会话只完成代码、聚焦自动化与编译最低门禁，不创建或替代独立 test record。

## 实际改动

1. 新增 `NewGameBackendPurgeService`，统一清理 Python 日程快照、记忆检查点和 `BehaviorEngine` 同日幂等缓存；SQLite 删除使用事务，后续检查点清理失败时恢复日程行并返回稳定子域失败码。Unity 新游戏入口切换为 `new_game_backend_purge`，旧消息仅作兼容入口。
2. 新增 `NpcScheduleReplanTracker`，从 runtime coordinator 拆出 `(npc_id, game_day, base_revision)` 单飞、冻结快照引用、operation 匹配、135 秒超时、跨日取消和诊断终态。互动与运行时恢复共用该入口。
3. `UnitySaveService` 只在收到匹配 `world_snapshot_applied` 后发布可用于 replan 的快照引用；缺失或跨日引用在 Unity 本地以 `schedule_snapshot_reference_missing` 收口，不进入 planner。
4. replan 后端拒绝改为匹配 `NPC_DAILY_SCHEDULE_READY failed` 终态和稳定 failure reason，不再发送污染世界准备状态的普通 `GAME_ERROR`。Unity 只让匹配 operation 的终态清 pending，失败保留原日程。
5. coordinator 增加跨日原子替换入口，按顺序取消旧任务、取消旧 pending、清理 candidate 关联、退役旧 controller 身份并接收新日 revision；controller 只比较同日 revision。
6. planner candidate DTO 新增显式 `required_group_id`。解析器接受确定性排序和完全重复去重；非 object、未知 candidate、非法时间、同时间冲突与 required group 缺失仍拒绝。LLM 和 fallback 共用 `validate_selection`，稳定 failure code 不再暴露异常类型。
7. 更新 NPC、协议与存档 Workstream 及相关代码目录 README，使当前口径与实现一致。

## 最低门禁

1. `python -m compileall -q backend/src`：通过。
2. Python 聚焦 pytest：20 passed，覆盖 planner/parser/required group/fallback、物理快照、记忆检查点与新游戏复合清理。
3. Unity MCP 脚本刷新与编译：通过；Console error 0。
4. Unity EditMode `NpcDailyScheduleTests`：7 passed、0 failed、0 skipped。
5. `git diff --check`：通过（仅现有 Windows 行尾转换提示，无 whitespace error）。
6. codebase-memory：canonical `AISc` 增量结果抽查陈旧且 full worker 两次崩溃；改用 `AISc_refresh_20260719` 完成 6191 nodes / 19797 edges 的 moderate 新鲜索引，并抽查命中 `NpcScheduleReplanTracker`。该工具异常已同步到索引状态文档。

## 未覆盖项

1. 未在本执行会话运行真实 PlayMode 长链、白名单 probe 或真实供应商 5 NPC 生成；这些必须在独立测试会话按 plan 验收。
2. 未修改场景、Prefab、SerializeField、UI 或其他 Unity 资产。
3. 后端自动重连、替代 spot DTO、真实动画完成事件与自然社交触发率仍不在本案范围。
