# 第二方案午夜平衡与完整性能诊断：执行记录

> 本轮为后端隔离调参与性能诊断，未创建 plan；未修改正式运行参数或业务代码。

## 测试目标

1. 为 `nightly_impression / llm_guided_local` 找到本地深搜预算平衡点。
2. 使用真实 Day 4 图、短期记忆和真实 LLM 执行一次完整午夜维护，定位阶段瓶颈。
3. 正式 `backend/data/game.db`、正式 LanceDB 和 Unity 运行态不参与测试。

## 第二方案参数平衡点

使用 `docs/AIChanges/artifacts/memory_route_day4_current_source/` 的 Day 4 图，对 5 名 NPC 到其余 NPC / 玩家的 25 个午夜目标组合进行预算扫描。方向阶段使用固定合法响应，以隔离本地图预算的影响；超高预算档作为本地图召回参考。

建议参数：

| 参数 | 当前值 | 平衡值 |
|---|---:|---:|
| `max_depth` | 9 | 8 |
| `beam_width` | 12 | 12 |
| `max_neighbors_per_node` | 20 | 16 |
| `max_expanded_edges` | 128 | 48 |
| `max_anchor_count` | 6 | 6 |
| `max_answer_candidates` | 20 | 20 |
| `min_path_score` | 0.18 | 0.18 |
| `early_stop_margin` | 0.12 | 0.12 |

平衡档结果：25/25 请求成功；平均展开 20.6 条边，最大 34 条；每个请求均返回 6 条记忆；本地检索中位约 204 ms、P95 约 275 ms。与超高预算参考相比，平均节点保持率为 98.67%，23/25 完全一致，最差保持 5/6。

临界证据：`beam_width=10` 或 `max_depth=7` 时平均保持率均降到 94%，低于 95% 目标；因此本轮不建议继续降低宽度或深度。正式 `backend/config/memory_retrieval.yaml` 尚未修改。

## 完整午夜模拟

测试产物：

- `docs/AIChanges/artifacts/2026-07-17_midnight_full_profile/midnight_full_profile.log`
- `docs/AIChanges/artifacts/2026-07-17_midnight_full_profile/midnight_full_profile_summary.json`
- 同目录 `data/` 为本轮隔离 SQLite / LanceDB 结算后副本。

运行上下文：Day 4 `24:00`，模型 `openai/LongCat-2.0`，调用正式 `GameRuntime.on_midnight(send_trigger=False)`，完整执行衰减、提取、图演化、印象/状态刷新和短期记忆清理。

| 阶段 | 耗时 | 总耗时占比 |
|---|---:|---:|
| `edge_decay` | 0.01s | <0.1% |
| `event_extraction` | 47.05s | 30.4% |
| `graph_evolution` | 7.92s | 5.1% |
| `impression_state` | 99.72s | 64.4% |
| `stm_cleanup` | 0.19s | 0.1% |
| 合计 | 154.89s | 100% |

结算前后：节点 `119 -> 138`，边 `128 -> 127`，短期记忆 `24 -> 19`，午夜检索日志 `200 -> 225`。完整流程返回成功，但存在一项局部提取失败，不能把本轮视作无错误结算。

## 瓶颈结论

1. 第一瓶颈是 `impression_state`：25 次 `memory_direction` 和 25 次 `nightly_impression`，占总耗时 64.4%。每名 owner 的 5 个目标并发，但 5 名 owner 在 `nightly_refresh()` 中串行处理，形成 5 个连续批次。
2. 第二瓶颈是 `event_extraction`：仅 1 次 `memory_extract` 就耗时 47.05s，其中供应商响应约 38.8s，随后首次加载 BGE 还产生约 7.9s 冷启动成本。
3. `graph_evolution` 只进行 1 次 `memory_merge`，耗时 7.92s；衰减和清理不是优化重点。
4. 本地深搜约 0.2s/次，不是当前午夜墙钟主因。把搜索预算改为平衡档主要降低最坏图扩张风险，无法单独显著缩短 154.89s 总耗时。

## 同轮发现的正确性问题

`kazuha` 的 `memory_extract` 返回后出现 `提取失败 (kazuha): 'from'`。`backend/src/memory/manager.py` 前置扫描使用 `edge.get("from", "")`，但正式写边阶段又直接读取 `edge["from"]` / `edge["to"]`；供应商返回缺字段边时因此触发 `KeyError`。本轮没有修复该问题，也没有为失败输入保存原始 LLM 内容。

## 优化优先级

1. 先修提取边缺字段的校验/跳过路径，并增加结构化失败计数，避免完整午夜表面成功但单 NPC 数据丢失。
2. 再评估把 5 名 owner 的印象批次并发化，或把“方向理解 + 印象生成”合并/缓存；必须设置全局并发上限，不能直接把 25 组全部并发打向供应商。
3. 提前预热 embedding，可从首次午夜移除约 8 秒冷启动，但不能解决主要 LLM 等待。
4. 采用本轮平衡搜索预算控制图规模增长后的最坏成本；预计当前 Day 4 数据上的直接墙钟收益较小。

## 验证与适用边界

- 完整午夜真实 LLM：成功完成一次，总耗时 154.89s。
- 本地预算扫描：25 个真实图组合，多档参数对照。
- `aisc_debug` / `aisc_control`：不适用。本轮未启动 Unity，且后端日志、结构化 summary 与隔离数据库已覆盖阶段、失败原因和关联模式。
- 单次供应商样本受网络和模型负载影响；阶段结构与调用数量可信，绝对耗时仍需至少再复跑 2 次才能形成 P50/P95。

