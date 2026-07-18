# 日程三层候选与记忆证据深化执行记录

> 设计方案: [2026-07-18_日程三层候选与记忆证据深化_plan.md](2026-07-18_日程三层候选与记忆证据深化_plan.md)

## 实际改动

- 扩展 `ScheduleCandidate` 为可解释 DTO，记录时间窗、世界状态、位置成本、来源、相关度分量与安全记忆证据字段。
- 将关闭、不可达、不可用 spot 和不适用天气在候选阶段确定性排除；职业、routine 与基础 need 不因记忆缺失被删除。
- 新增 `schedule_memory_evidence.py`，按 owner 的候选组调用现有 `RetrievalEngine.retrieve`，仅回写 evidence ID、相似度、图路径分和 trace ID。
- `DailySchedulePlanner` 保持每名 NPC 一次 LLM 调用，并在解析后统一验证候选归属、required 保留、时间递增、窗口和物理状态；任一失败整体 fallback。
- fallback 使用稳定种子，记录入选和因目标数量淘汰的原因；owner trace 记录物理拒绝、记忆统计、fallback 原因和超时迟到隔离状态。
- `BehaviorEngine` 仅提供 retrieval facade 与只读诊断 facade；新增 `/api/npc/daily_schedule_trace` 供 `aisc_debug` 查询。

## 文档与边界

- 回写 `docs/AIChanges/NpcBehavior/README.md` 和 `backend/src/npc/README.md`。
- 未修改 Unity 场景、Prefab、SerializeField 或执行状态机；未引入 visitor/host 原子预约或通用多人资源求解。傍晚跨 NPC 协调保留给后续 Unity 日程执行阶段。

## 验证

- `python -m unittest backend.tests.test_daily_schedule_planner backend.tests.test_schedule_candidates backend.tests.test_schedule_world_snapshot`
- 结果：8 项通过。

## 未完成项

- 真实供应商下的 5 owner、120 秒超时长尾，以及 Unity Play Mode 跨 NPC 傍晚错峰，须按后续执行案在编辑器稳定连接时验收。
