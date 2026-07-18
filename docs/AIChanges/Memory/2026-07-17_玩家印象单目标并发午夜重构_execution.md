> 设计方案: [2026-07-17_玩家印象单目标并发午夜重构_plan.md](2026-07-17_玩家印象单目标并发午夜重构_plan.md)

# 玩家印象单目标并发午夜重构：执行记录

## 实际改动

1. 新增 `backend/src/memory/midnight_coordinator.py`，把路由冻结、双重阶段并发、图演化、顺序提交、次日状态刷新、清理和结构化诊断从 `GameRuntime` 中拆出。
2. 新增 `backend/src/npc/player_impression_refresh.py`，只为 5 名非玩家 NPC 准备和生成 `NPC -> player` 印象；工作线程只返回纯结果，SQLite 由协调线程顺序提交。
3. `StateManager.nightly_refresh()` 改为兼容委托，不再自行遍历 25 个 owner-target 组合。NPC-NPC 基准印象与白天 delta 不在午夜重建或清空。
4. `RetrievalRequest` 增加受控固定方向输入；午夜以 `direction_source=nightly_fixed_player` 使用正式本地图检索，`memory_direction` 调用为 0。白天三种公开策略不变。
5. `nightly_impression` policy 改为显式 `local_only`，图预算锁定为 `8 / 12 / 16 / 48 / 6 / 20 / 0.18 / 0.12`；检索 trace 同步输出关键预算。
6. 玩家印象生成和事件提取通过 `asyncio.gather(..., return_exceptions=True)` 重叠执行；图演化等待提取结束，之后才提交玩家印象。
7. 次日 `sociability_baseline` 只使用 profile `social_base`、当日 `sociability_delta` 和受限玩家 `approach_bias`，不再平均陈旧 NPC-NPC 基准。
8. 事件提取缺 `from`、缺 `to`、未知临时 ID 或未知持久节点 ID 时计数并跳过；合法节点和合法边继续写入。
9. 午夜快照覆盖 operation ID、阶段、`success / partial_failure / failed`、固定方向来源、每 owner trace、印象和提取计数、非法输出、失败 owner、并发墙钟和阶段耗时。`partial_failure` 同步进入跨日完成协议。
10. Unity 增加 `aisc_debug.midnight_snapshot` 和编辑器白名单 `aisc_control.run_midnight_settlement`；控制入口复用正式 `SleepController`，未新增场景、Prefab、SerializeField 或 UI 资产连线。

## 文档与索引回写

已同步：

- `docs/Workstreams/Memory/README.md`
- `docs/Workstreams/NpcBehavior/README.md`
- `backend/src/memory/README.md`
- `backend/src/npc/README.md`
- `Assets/Scripts/Diagnostics/README.md`
- `docs/AIChanges/Memory/README.md`

ADR-0001 的轻量图 / 向量边界未改变，不新增 ADR。

## 自动化验证

1. `python -m compileall backend/src`：通过。
2. `PYTHONPATH=. pytest -q backend/tests`：`97 passed, 3 subtests passed`。
3. `dotnet build AISc.sln --no-restore`：0 错误；9 条既有程序集版本冲突 / 未赋值字段警告。
4. Unity MCP 强制刷新：成功，最终 Console error 为 0。
5. Unity MCP EditMode `AiscDiagnosticsTests`：14/14 通过。
6. 协调器测试证明玩家印象与提取分支实际重叠，且顺序为 `extraction end -> graph evolution -> commit`。
7. 非法边测试覆盖缺 `from`、缺 `to`、未知临时 ID、未知持久 ID 和合法已有 ID。

## Day 4 隔离真实 LLM 复跑

数据源：`docs/AIChanges/artifacts/memory_route_day4_current_source/`。每轮先复制 SQLite 和 LanceDB，再只运行副本。汇总见 `docs/AIChanges/artifacts/2026-07-17_midnight_single_player_concurrency/summary.json`。

权威 SQLite SHA-256 前后均为：

`5DE8D34C9B3577960BFB0D52369C3A307BB4D8E32F00E357C0AFA47C83A1E98C`

| 轮次 | 完整午夜 | 并发墙钟 | 玩家印象生成 | 事件提取 | 图演化 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| 1 | 93.08s | 25.04s | 6.65s | 25.04s | 56.71s | success |
| 2 | 37.26s | 20.11s | 6.83s | 20.11s | 5.83s | success |
| 3 | 36.64s | 19.09s | 12.48s | 19.09s | 6.41s | success |

P50 为 `37.26s`，达到不高于 65s 的目标。首轮长尾来自 `graph_evolution` 的供应商调用，不是印象与提取重新串行。

三轮共同结果：

1. 玩家印象计划数 / 非空结果均为 5，fallback 为 0。
2. 夜间方向调用为 0；每轮新增 5 条夜间检索日志，`llm_route_calls` 合计为 0。
3. 数据库中只有 5 条 `NPC -> player` 印象发生变化；NPC-NPC 行无变化。
4. 5 条玩家关系 delta 均被清空，其他目标未被午夜提交路径触碰。
5. 并发墙钟等于或接近事件提取这一较慢分支，而不是两分支之和。
6. 非法边分别计数 12 / 8 / 0，均未中断合法提取。
7. 路由预算沿用本 plan 已确认的真实图保持率证据：平均 `98.67%`，不重新调整到 `7 / 10`。

## 执行中发现并修正的问题

首次探针直接使用 `cfg.config.npc_ids` 时发现该集合包含 `player`，会错误计划第 6 条 `player -> player` 印象。根因是旧 `StateManager` 使用固定 5 NPC 列表，而新模块最初继承了更宽的配置集合。现已在 `PlayerImpressionRefresher` 所有入口统一过滤 `player`，并增加回归测试。该探针不计入 3 轮验收；其隔离副本因本机删除策略拒绝而保留为 `run_invalid_6owners/`，summary 明确标记 `counted_in_acceptance=false`。

## 风险与未完成项

1. NPC-NPC 长期关系不再每日压缩，继续接受 plan 已确认的叙事精细度取舍。
2. 首轮 `graph_evolution` 出现 56.71s 供应商长尾；P50 达标，但单轮最坏值仍可能超过 65s。
3. 本轮未在 Unity Play Mode 直接触发正式午夜。原因是当前编辑器连接正式运行配置，直接控制会修改正式数据库，违反隔离快照要求；后端已用同源隔离副本完成 3 次真实 LLM 完整午夜，Unity 控制 / DTO 通过编译与 EditMode 测试。后续 Play Mode 验证必须先把后端切到隔离副本，再使用 `aisc_control.run_midnight_settlement` 和 `aisc_debug.midnight_snapshot`。
