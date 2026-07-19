# NPC 日程过期 replacement 修复执行记录

关联方案：[2026-07-19_NPC日程PlayMode缺口收口_plan.md](2026-07-19_NPC日程PlayMode缺口收口_plan.md) 第 13.5.5 条。

独立复测：[2026-07-19_NPC日程PlayMode缺口收口_test.md](2026-07-19_NPC日程PlayMode缺口收口_test.md) 的“有界复测：NPC 日程冻结快照 revision 污染修复”；当前失败结论保留，等待后续测试会话追加复测。

## 根因

`DailySchedulePlanner._prepare_owner` 同时服务整日规划和 replan，但最终校验没有冻结请求时间下界；LLM 成功结果可接受早于当前 replan 时间的 `planned_start_time`，fallback 也只依据候选建议时间和合法窗口排程，因而会把已经错过的 `08:00 work_open` 再次放入 replacement。

## 实际改动

- `validate_selection` 增加可选 `minimum_start_minute`，早于 operation 冻结时间的选择以 `schedule_start_before_operation` 整体拒绝。
- 互动 replan 和运行时恢复 replan 从同一 `GameTimeSnapshot` 计算时间下界；开局和跨日整日规划保持原行为。
- LLM 结果与确定性 fallback 共用该下界；fallback 从当前分钟或之后生成严格递增 replacement。
- 新增聚焦回归，覆盖 provider 返回合法候选但时间已过期时，最终 replacement 全部不早于冻结请求时间。

## 最低门禁

- `python -m pytest backend/tests/test_daily_schedule_planner.py -q`：9 passed。
- `python -m compileall -q backend/src/npc backend/tests/test_daily_schedule_planner.py`：通过。
- 未执行真实 Unity PlayMode；该证据属于后续独立测试会话。

## 文档与索引

- 更新后端 NPC README 和 NPC Behavior Workstream 的时间下界口径。
- 更新本主题 plan、test 和功能目录 README 的互链；`ChangeIndex.md` 只路由到功能目录，无需增加日期条目。

## 结论

实现完成，待独立测试。需要在稳定连接的真实 PlayMode 中证明同一错过 candidate 不再出现、schedule revision 稳定、pending 释放，并保持 `schedule_snapshot_version_mismatch=0`。
