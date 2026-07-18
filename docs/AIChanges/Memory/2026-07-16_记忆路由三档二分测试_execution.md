> 设计方案: [2026-07-16_记忆路由三档二分测试_plan.md](2026-07-16_记忆路由三档二分测试_plan.md)

# 记忆路由三档二分测试 - 执行记录

## 实际改动

1. 新增 `backend/scripts/tune_memory_route_profiles.py`：复制正式 SQLite/LanceDB 到隔离目录，从真实图采样候选边，重复调用真实 LLM 建立稳定基线，并沿单调激进度轴二分搜索阈值。
2. 新增 `backend/tests/test_memory_route_profiles.py`：覆盖激进度单调性、选边重合度、性能/效果统计和二分边界。
3. 生成 `docs/AIChanges/artifacts/memory_route_profiles/memory_route_profiles.json` 与 `.md`，保存原始候选、三次 LLM 选择、延迟、稳定度和三档结果。
4. 回写 Memory Workstream 与后端脚本 README。
5. 记录并索引 Windows 下并行 Python 命令争写 `__pycache__` 的可复用错误。

## 三档定义

1. 性能：二分搜索效果保持率不低于 75% 的最大本地路由激进度。
2. 平衡：二分搜索效果保持率不低于 95% 的最大本地路由激进度。
3. 质量：设置 `min_score=999`、`margin=999`，禁用本地自信跳过，始终使用 LLM 路由。

首轮使用 90% / 95% / 99% 时，当前小图的离散质量台阶让三个档位落到同一阈值。检查样本后确认质量会从 100% 直接跳到 75%，因此性能档改用 75% 下限；质量档改为始终 LLM，保证三个玩家选项语义真实。

## 实测结果

测试模型：`deepseek/deepseek-chat`。

每种模式采集 8 个真实图候选集，每个候选集调用 LLM 3 次，共 24 个样本、72 次 LLM 路由调用。

| 模式 | 档位 | min_score | margin | 效果保持率 | LLM 节省率 | 预计平均路由延迟 |
|---|---|---:|---:|---:|---:|---:|
| player_dialogue | 性能 | 0.000 | 0.000 | 75.0% | 100.0% | 0.000s |
| player_dialogue | 平衡 | 0.045 | 0.015 | 100.0% | 50.0% | 0.354s |
| player_dialogue | 质量 | 999.000 | 999.000 | 100.0% | 0.0% | 0.708s |
| npc_dialogue | 性能 | 0.000 | 0.000 | 75.0% | 50.0% | 0.353s |
| npc_dialogue | 平衡 | 0.045 | 0.015 | 100.0% | 0.0% | 0.706s |
| npc_dialogue | 质量 | 999.000 | 999.000 | 100.0% | 0.0% | 0.706s |
| nightly_impression | 性能 | 1.725 | 0.575 | 75.0% | 50.0% | 0.359s |
| nightly_impression | 平衡 | 2.280 | 0.760 | 100.0% | 0.0% | 0.718s |
| nightly_impression | 质量 | 999.000 | 999.000 | 100.0% | 0.0% | 0.718s |

LLM 基线稳定度：

1. `player_dialogue`：100.0%。
2. `npc_dialogue`：93.8%。
3. `nightly_impression`：94.4%。

## 结论

当前默认建议选择“平衡”档：玩家对话可减少约 50% LLM 路由，同时在本轮样本中保持 100% 选边效果；NPC 闲聊和夜间印象不应激进本地化，因为当前本地评分对宽联想语义的判断明显弱于 LLM。

性能档适合低成本或离线运行，但会产生约 25% 的选边差异。质量档适合对叙事一致性要求最高、可接受完整 LLM 延迟与成本的运行方式。

## 验证

1. `python -m py_compile backend/scripts/tune_memory_route_profiles.py backend/tests/test_memory_route_profiles.py`：通过。
2. `python -m unittest backend.tests.test_memory_route_profiles -v`：4 项通过。
3. 两轮真实 LLM 跑测均完成；最终报告使用第二轮固定基线。
4. 正式 `backend/data/game.db` 跑测前后 SHA-256 一致，结果字段 `source_database_unchanged=true`。
5. 测试全程使用隔离 SQLite 与 LanceDB 副本。

## 诊断钩子说明

本轮只测试后端记忆检索路由，没有启动 Unity 运行态，也没有修改 Unity 业务语义，因此 `aisc_debug` 的 `runtime_snapshot` 等动作不适用。路由候选、LLM 选择、稳定度、阈值和性能数据均已写入结构化 JSON 产物。

## 未完成项

1. 当前每模式只有 8 个有效候选集，图规模扩大或记忆分布改变后需要重跑。
2. 本轮没有把三档配置接入正式玩家设置 UI，也没有修改 `RETRIEVAL_MODE_CONFIGS` 当前默认值。
3. 预计平均路由延迟只按 LLM 调用占比估算，本地评分耗时接近零但未单独展示 P95。

## Day 4 真实运行数据复测

使用 `docs/AIChanges/artifacts/memory_route_day4_current_source/` 作为独立数据源，测试上下文为 `Day 4 09:38 / player_cafe.kitchen`。每模式采集 12 个候选集，每个候选集调用 LLM 3 次，共 36 个样本、108 次真实 LLM 路由。

脚本新增 `--source-db`、`--source-lancedb`、`--game-time` 和 `--player-location`，可以复用固定运行快照，不再读取正在变化的正式数据目录。

### 三档结果

| 模式 | 档位 | 效果保持率 | LLM 节省率 | 平均 LLM 延迟 |
|---|---|---:|---:|---:|
| player_dialogue | 性能 | 79.2% | 83.3% | 0.908s |
| player_dialogue | 平衡 | 95.8% | 50.0% | 0.908s |
| player_dialogue | 质量 | 100.0% | 0.0% | 0.908s |
| npc_dialogue | 性能 | 75.0% | 50.0% | 0.880s |
| npc_dialogue | 平衡 | 95.8% | 8.3% | 0.880s |
| npc_dialogue | 质量 | 100.0% | 0.0% | 0.880s |
| nightly_impression | 性能 | 100.0% | 0.0% | 1.053s |
| nightly_impression | 平衡 | 100.0% | 0.0% | 1.053s |
| nightly_impression | 质量 | 100.0% | 0.0% | 1.053s |

### 当前正式阈值直接评估

| 模式 | 当前 min_score / margin | 效果保持率 | LLM 节省率 | 判断 |
|---|---|---:|---:|---|
| player_dialogue | 1.25 / 0.35 | 100.0% | 0.0% | 过于保守，实际没有使用本地路由 |
| npc_dialogue | 1.15 / 0.30 | 100.0% | 0.0% | 没有使用本地路由 |
| nightly_impression | 1.20 / 0.25 | 50.0% | 50.0% | 本地接管过于激进，不应继续沿用 |

### 使用建议

1. `player_dialogue`：使用本地/LLM 混合路由，建议平衡阈值约 `0.045 / 0.015`；本轮保持 95.8% 效果并节省 50% LLM。
2. `npc_dialogue`：优先使用 LLM。平衡档只能节省 8.3%，不足以抵消规则复杂度和小样本风险。
3. `nightly_impression`：使用 LLM，不启用本地自信跳过。当前正式阈值在本轮样本中效果保持率只有 50%。

本轮只形成复测结论，未修改 `RETRIEVAL_MODE_CONFIGS` 正式运行阈值。
