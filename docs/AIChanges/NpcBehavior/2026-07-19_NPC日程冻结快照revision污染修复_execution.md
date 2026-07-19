# NPC 日程冻结快照 revision 污染修复执行记录

关联方案：[2026-07-19_NPC日程PlayMode缺口收口_plan.md](2026-07-19_NPC日程PlayMode缺口收口_plan.md) 第 13 节。

独立复测：[2026-07-19_NPC日程PlayMode缺口收口_test.md](2026-07-19_NPC日程PlayMode缺口收口_test.md) 的“有界复测：NPC 日程冻结快照 revision 污染修复”。

## 实际改动

- `GameCommandSender.SendNpcScheduleReplanRequest` 移除独立 `worldRevision` 参数。
- 新增 `BuildNpcScheduleReplanRequestCommand`，从同一 `NpcScheduleSnapshotReference` 投影 `snapshot_id/time_revision/world_revision`。
- `GameManager` 唯一调用点不再传入当前 `WorldRevision`。
- 新增 EditMode 回归用例，覆盖冻结引用为 `s1/2/3` 且当前态 revision 不参与命令构造。

## 最低门禁

- Unity MCP 刷新并请求脚本编译：成功，编辑器恢复就绪。
- Unity EditMode 测试任务：任务成功，未返回单测明细（Unity 测试筛选器将测试程序集汇总为 `AISc`）。
- `git diff --check`：通过。
- codebase-memory：已建立 `AISc_replan_fix_20260719` moderate 持久化索引（6219 nodes / 19928 edges）。

## 结论

修复实现完成，待独立复测。真实 PlayMode 与正式协议三元组证据不在本执行会话内完成。
