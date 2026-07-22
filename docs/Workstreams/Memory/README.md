# 工作流：记忆系统

## 当前目标

保持 v0.7 轻量图记忆工程口径，优先提升可信度、诊断能力和长测质量，不把旧 v0.5 远期设想当作近期实现清单。

## 当前工程口径

1. 每个 NPC 独立维护图。
2. SQLite 图层保存节点 ID、边、边类型和双向 clarity。
3. LanceDB / SQLite 向量层保存节点内容、embedding、importance、created_day、archived。
4. 图负责联想路径，向量层负责语义内容和兜底。
5. 白天按 `player_dialogue` / `npc_dialogue` 模式轻量检索。
6. 夜间只刷新 5 条 `NPC -> player` 基准印象；事件提取前用 `nightly_fixed_player` 固定方向冻结更宽的本地图检索结果，夜间 `memory_direction` 调用为 0。
7. 当前遗忘机制以边 clarity 衰减 + archived 归档为主。
8. 记忆相关 LLM 调用不设置 `max_tokens` 硬上限；输出格式与规模由 Prompt 软约束，并由解析和业务校验收口。

## 已完成阶段

1. BGE 向量图记忆系统。
2. 双向边语义。
3. 多跳图路由对话检索。
4. 夜间印象多跳图路由。
5. 玩家背景长期记忆化。
6. 图记忆时间语义修正。
7. 节点融合边继承。
8. 记忆图可信度增强。
9. 设计文档 v0.7 当前口径追平。
10. 已用 Day 4 真实运行图与真实 LLM 复测旧本地/LLM 路由；公开策略仍为 `local_only`、`llm_guided_local`、`llm_full_route`。默认玩家=引导深搜、NPC-NPC=完全本地；午夜固定玩家目标通过受控方向走 `local_only`，参数锁定为 `max_depth=8`、`beam_width=12`、`max_neighbors_per_node=16`、`max_expanded_edges=48`。九组合离线评估入口为 `backend/scripts/evaluate_deep_retrieval.py`。
11. 玩家正式对话检索已在每轮使用最新发言和近期对白重新路由；图起点保持既有策略，不再由话题实体扩张，也不在路由前预查话题人物关系。
12. 午夜重阶段由 `MidnightCoordinator` 编排：玩家印象生成与事件提取并发，图演化等待提取结束，玩家印象由协调线程顺序提交；NPC-NPC 基准和 delta 不在午夜重建或清空。
13. R3 v2 运行时接入及其独立验收证据继续保留，但 A/B/C 实验已选择 C：玩家、NPC-NPC 与午夜正式默认均切为 `local_only + [local]`，生产 provider 注册表不再注册或预热 R3 worker。实时检索由 `LocalDirectionProvider` 与 `RetrievalQueryPlanner` 确定性构造唯一 embedding query；`general_llm`、显式 R3 测试能力和 `llm_full_route` 仍保留。

## 下一阶段建议

1. 做玩家事件前端触发点，让真实玩家行动进入短期记忆。
2. 增加检索诊断 UI 或调试面板。
3. 做融合质量评估和可达性统计。
4. R3 v2 约 9-11 秒热路径是切换到零 LLM 默认路线的历史原因；后续用 Unity 实际对话补充首轮、后续轮墙钟与 p95 证据，不把专项模型重新放回默认链。默认策略与参数配置见 `backend/config/memory_retrieval.yaml`。
5. 修日计划非法空 location 对记忆和行为链路的干扰。
6. 前端正常流程、协议 / 存档底座和夜间主流程稳定后，再实现概率化节点融合：
   - 用“融合可能性 + 午夜概率抽签”替代单纯高相似度硬阈值。
   - 融合可能性同时考虑节点年龄、入边 clarity 平均值、向量相似度和旧记忆混淆压力。
   - 低相似度不设硬保护，特别旧且模糊的节点可发生混淆式融合。
   - 混淆式融合结果必须保持模糊印象口径，不生成确定新事实。

## 后续优化计划案：概率化节点融合

### 排期位置

该项属于后端记忆优化，不插队当前前端正常流程。

前置条件：

1. 前端正常流程可以从启动、移动、对话、时间推进跑完。
2. 协议 / 存档底座稳定。
3. 夜间主流程可以稳定完成衰减、短期记忆入图、图演化和印象刷新。

### 目标

把当前 `similarity >= 0.85` 的硬阈值融合，改成午夜运行的概率模型：

```text
午夜衰减
→ 短期记忆入图
→ 构建融合候选池
→ 计算 merge_likelihood
→ 按 merge_probability 抽签
→ semantic_merge / confusion_merge
→ 生成融合节点
→ 继承旧边并归档来源
```

目标行为：

1. 新节点基本不融合。
2. 清晰节点不容易融合。
3. 旧且模糊节点会自然融合。
4. 低相似度不设硬保护，特别旧且模糊的节点允许发生混淆式融合。
5. 混淆式融合只生成模糊印象，不能生成确定新事实。

### 融合可能性公式

```text
merge_likelihood(A, B)
= age_gate
  * type_gate
  * (
      0.52 * decay_pressure
    + 0.28 * semantic_pressure
    + 0.20 * confusion_pressure
    )
```

第一版只允许同类型 event 节点融合：

```text
type_gate = 1.0  if type(A) == type(B) == "event"
type_gate = 0.0  otherwise
```

年龄项：

```text
age(A) = current_day - created_day(A)
age(B) = current_day - created_day(B)

min_age = min(age(A), age(B))
avg_age = (age(A) + age(B)) / 2

age_gate = smoothstep(14, 45, min_age)
oldness = smoothstep(45, 365, avg_age)
```

含义：

1. 14 天内基本不融合。
2. 14 到 45 天逐步开放融合。
3. 45 天后正常参与。
4. 365 天左右达到强旧记忆压力。

清晰度项按“所有指向该节点的边 clarity 平均值”计算。边少的新节点不能被误判成模糊，所以加入默认清晰先验：

```text
node_clarity(n)
= (sum(incoming_clarity(n)) + 3 * 0.85)
  / (incoming_edge_count(n) + 3)

pair_clarity = (node_clarity(A) + node_clarity(B)) / 2
uncertainty = 1 - pair_clarity
```

衰退压力：

```text
decay_pressure = max(oldness ^ 1.35, oldness * uncertainty)
```

语义压力：

```text
dynamic_threshold = 0.86 - 0.30 * oldness - 0.20 * uncertainty
semantic_pressure = sigmoid((similarity - dynamic_threshold) / 0.08)
```

混淆压力：

```text
confusion_pressure = oldness * uncertainty * random(0.65, 1.0)
```

最终抽签概率：

```text
merge_probability = clamp(merge_likelihood ^ 1.2, 0.0, 0.85)
```

辅助函数：

```text
smoothstep(edge0, edge1, x):
  t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
  return t * t * (3 - 2 * t)

sigmoid(x):
  return 1 / (1 + exp(-x))
```

### 融合类型

```text
if similarity >= 0.65:
  merge_mode = semantic_merge
else:
  merge_mode = confusion_merge
```

`semantic_merge`：

1. 生成较明确的概括记忆。
2. 允许保留相似事件的共同人物、地点、情绪或行为。
3. 继承边 clarity 不额外削弱。

`confusion_merge`：

1. 生成模糊、印象化、低确定性的混合记忆。
2. 不允许断言具体因果、精确时间、精确地点或新人物关系。
3. 继承边 clarity 建议乘以 `0.65`，避免混淆记忆变成过强检索路径。

### 候选池策略

第一版不做全图两两融合，控制午夜性能：

1. 只取 active event 节点。
2. 过滤 `min_age < 14` 的候选。
3. 按 `oldness * uncertainty` 排序，取 Top 24。
4. 对 Top 24 做 pairwise similarity，不设置最低相似度过滤。
5. 每个 NPC 每晚最多融合 2 到 5 对。
6. 每个节点每晚最多参与一次融合。
7. 没有可继承外部边的候选不融合，避免制造孤点。

### 实现落点

后续真正实施时，优先在现有融合闭环上小步替换：

1. `backend/src/memory/evolution.py`
   - 保留现有边继承和旧节点归档逻辑。
   - 将 `_merging()` 拆出候选收集、清晰度计算、可能性计算、抽签、prompt 构造等小函数。
   - 避免继续把所有状态和分支堆在一个过重函数里。
2. `backend/src/memory/embedding.py`
   - 当前 `pairwise_similarities()` 只返回 `>0.7` 的 pair。
   - 新增或调整为支持“不设最低阈值”的 pairwise similarity，供混淆式融合使用。
3. `backend/src/database/sqlite_client.py`
   - 复用 `get_edges_touching_node_ids()` 计算节点入边 clarity。
   - 如需诊断，再考虑补融合抽签日志表；第一版不强制扩 schema。
4. `memory_merge_sources`
   - 继续记录来源节点和 similarity。
   - 后续如需诊断，可扩展记录 `merge_mode`、`merge_likelihood`、`merge_probability`。

### 验证标准

后续实现时至少覆盖：

1. 新节点 + 高相似度：不融合。
2. 旧节点 + 高相似度：高概率 `semantic_merge`。
3. 旧节点 + 低相似度 + 低 clarity：可能 `confusion_merge`。
4. 混淆式融合结果不出现新的确定事实。
5. 融合节点继承旧邻边，旧图节点退场，旧向量节点 archived。

## 暂缓事项

1. 完整四阶段退化。
2. 全图 `similar_to` 建边。
3. 节点 energy / precision 等复杂认知本体扩张。
4. 围绕旧 v0.5 文本做追齐式开发。

## 相关设计与决策

1. `docs/DesignDocs/MemoryArchitecture.md`
2. `docs/DesignDocs/memory/graph-memory-model.md`
3. `docs/DecisionRecords/ADR-0001-memory-v07-light-graph.md`

## 专项草案

1. `InitialGraphSemanticRoutingFixDraft.md`：初始人物关系 clarity 与明确话题实体图路由修复的草案来源；已落档执行案 `docs/AIChanges/Memory/2026-07-17_初始图语义路由修复_plan.md`，执行记录见同目录 `_execution.md`。
2. `InitialKnowledgeProjectionDraft.md`：冷启动初始知识投影与他人记忆衍生草案；执行案为 `docs/AIChanges/Memory/2026-07-17_冷启动初始知识投影_plan.md`，执行记录见同目录 `_execution.md`。
3. `LlmGuidedLocalDeepRetrievalDraft.md`：三模式可配置记忆路由的需求来源；执行案和记录见 `docs/AIChanges/Memory/2026-07-17_LLM定向本地深层记忆检索_plan.md` 与对应 execution。执行案提供 `local_only`、`llm_guided_local`、`llm_full_route`，默认玩家=引导深搜、NPC-NPC=完全本地、夜间=高预算引导深搜。
4. `LlmRetrievalQueryVectorRoutingFixDraft.md`：LLM 检索想法与原问题、至多一条相关近期对白组成单次向量 query，并由本地实体校准、图路由和最终原子条目选择收口的设计来源；已按 `docs/AIChanges/Memory/2026-07-17_LLM检索想法向量路由修复_plan.md` 实施，执行证据见同目录对应 execution。
5. `MemoryRoutingSpecialistModelSwitchDraft.md`：用 `Qwen3-0.6B + Route LoRA` 首测替代 `memory_direction` 通用 LLM，并通过 Python 离线、shadow、回退和 golden corpus 验证后再迁移 C# 的切换草案。
6. `MemoryMergeSpecialistModelSwitchDraft.md`：用与 R3 v2 共享冻结底模 runtime 的 `Qwen3-0.6B + Merge LoRA` 首测结构化、安全可拒绝的记忆融合，并保持独立 Adapter、validator、失败策略以及本地候选、概率、权限和事务权威。
7. `MemoryRouteR3V2RuntimeIntegrationDraft.md`：把已冻结的 R3 v2 作为 `llm_guided_local` 默认方向 provider、保留三种现有检索策略，并以可共享 0.6B 底模的常驻本地 worker、可配置 provider chain、稳定回退和独立检索级验收接入运行时的草案。
8. `MemoryRouteVectorQueryHintExperimentDraft.md`：先用 LongCat 对比完整方向 JSON、单句向量 query hint 和零 LLM 确定性 query；只有单句在检索质量、tokens 和延迟上同时胜出，才进入新本地 Adapter 训练，不直接修改现有 R3 v2 生产契约。

## 相关执行证据

详见 `docs/AIChanges/Memory/README.md`。
