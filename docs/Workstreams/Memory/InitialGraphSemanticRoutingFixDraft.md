# 初始记忆图与语义路由修复草案

## 1. 状态与范围

本文是待确认的修复草案，不是实施 plan，不代表已经授权修改代码。

目标是修复两个相互放大的问题：

1. 冷启动时把人物亲疏 `bond` 误当成记忆边 `clarity`，导致 NPC 对熟人的基础认知过低。
2. 玩家发言明确点名人物或地点时，语义相关性不足以对抗玩家背景事件的结构性加分，只能依赖向量兜底。

不扩张 ADR-0001 的轻量图模型，不新增完整认知本体，不改变“图负责联想路径、向量层负责语义内容与兜底”的系统边界。

## 2. 概念拆分

修复必须明确区分以下三个概念：

| 概念 | 含义 | 当前落点 | 修复原则 |
|---|---|---|---|
| `bond` | NPC 对目标的亲疏、态度和关系强度 | `npc_bonds`、人物配置 | 不再直接决定是否记得对方 |
| `clarity` | 沿某条图边进行联想的清晰程度 | `memory_edges.clarity_ab / clarity_ba` | 初始核心人物关系应有稳定认知下限 |
| semantic relevance | 候选节点与当前发言、近期对白的语义相关程度 | 图候选评分与向量检索 | 明确点名实体时应成为强排序信号 |

这三个值可以共同影响检索，但不得互相替代。

## 3. 修复方案

### 3.1 初始人物关系边

在 `backend/src/npc/state_manager.py` 初始化人物节点时，不再将 `bond_val` 作为 `resolve_edge_clarity()` 的 `target_importance` 参数。

建议由 `backend/src/memory/edge_semantics.py` 集中提供初始人物认知规则，例如：

```text
initial_relationship_clarity(
    recognition_importance=0.9,
    bond=bond_val,
    is_core_person=true,
) -> (clarity_ab, clarity_ba)
```

第一版建议：

1. `self -> person` 的认知 clarity 下限为 `0.72` 至 `0.80`。
2. `person -> self` 的反向联想下限为 `0.60` 至 `0.70`。
3. `bond` 只提供小幅修正，例如最多影响 `±0.08`，不能把基础认知压到接近遗忘阈值。
4. `target_importance` 继续表达人物节点的重要性，不复用为 bond。
5. 玩家、主要 NPC 和未来关键剧情人物统一通过规则模块处理，不在初始化函数里增加人物专属分支。

具体数值必须通过竞争型检索测试校准，以上范围不是最终常量。

### 3.2 图候选语义评分

保留 `RetrievalEngine` 作为检索 module，对调用者继续维持单一 `retrieve(request)` interface；语义解析、图候选评分和向量兜底都封装在该 module 内，不要求对话调用者编排多个步骤。

调整 `_score_candidate_edge()` 的评分结构：

```text
candidate_score
= graph_path_score
+ semantic_relevance_score
+ type_and_mode_score
+ target_context_score
```

建议改动：

1. 明确实体命中：当前发言完整包含候选人物名、地点名或稳定别名时，给予足以改变 Top-N 的强加分。
2. 普通文本相关：由 embedding 相似度或统一的轻量语义评分提供连续值，不再只依赖“共享字符集合”。
3. 结构加分限幅：`source_is_target`、反向 `involved`、event 类型和玩家背景关键词不能叠加到完全淹没当前话题。
4. 玩家背景提示只在没有明确话题实体，或候选本身与当前话题也相关时发挥主要作用。
5. 图候选语义评分负责决定走哪条边；向量兜底仍只在图结果不足时补节点，不替代图路径。

### 3.3 实体识别边界

第一版不引入新 NLP 基础设施，复用已有稳定 NPC 显示名映射和地点数据：

1. 当前发言中出现“千早”，识别为 `npc_id=chihaya`。
2. 对人物节点候选使用稳定 ID 与显示名共同匹配。
3. 地点实体使用现有 location ID / display name 映射。
4. 将实体匹配封装为私有纯函数或小型内部 module，输入文本、候选元数据，输出可测试的相关性结果。

未来若实体类型扩大到三种以上并持续增长，再提取统一实体目录 interface；本轮不提前引入复杂实体系统。

## 4. 最小回归 seam

优先通过 `RetrievalEngine.retrieve(RetrievalRequest)` 这一稳定 seam 写测试，不直接断言私有评分函数的内部常量。

### 4.1 冷启动规则测试

1. `bond=0.15` 的已知 NPC 关系边，clarity 仍高于基础认知下限。
2. 高 bond 可以提高关系语义，但不会让 clarity 超过合法上限。
3. 玩家与主要 NPC 使用同一抽象规则，不出现人物专属 switch / if 链。

### 4.2 真实竞争检索测试

构造接近九条莲当前图的最小数据：

1. 起点为“我”和“小李”。
2. 候选同时包含千早人物关系边、两个高 clarity 玩家背景事件和一个商店街背景事件。
3. 输入“你知道千早在哪里吗”。
4. 断言千早关系边进入选中路径，千早节点进入最终上下文。
5. 断言结果不依赖 `vector_fallback_used` 才找到千早。

同时增加反例：输入“喫茶店最近怎么样”，玩家喫茶店背景应继续优先，避免修复后所有人物名都产生过强吸附。

### 4.3 运行诊断验收

用 `aisc_debug.conversation_retrieval_snapshot` 验证：

1. `start_node_ids` 仍保持 self + 对话参与者，不把话题实体偷加成起点。
2. `selected_edge_ids` 包含被当前话题选中的人物关系边。
3. `retrieved_node_ids` 包含相关人物或地点节点。
4. 对明确实体问题，正常情况下 `vector_fallback_used=false`；图结果确实不足时仍允许兜底。
5. `failure_reason` 为空，工作记忆和持久化状态保持既有语义。

## 5. 预计涉及文件

实施时预计至少涉及：

1. `backend/src/memory/edge_semantics.py`：统一人物基础认知 clarity 规则。
2. `backend/src/npc/state_manager.py`：冷启动调用新规则，停止把 bond 直接当 clarity。
3. `backend/src/memory/retrieval.py`：调整候选语义评分与结构加分上限。
4. `backend/tests/test_conversation_memory_routing.py`：新增真实竞争场景。
5. 可能新增或扩展边语义单元测试；不为测试方便暴露私有实现。
6. 若诊断 DTO 已能表达选边、节点、向量兜底和失败原因，则无需新增钩子；若加入新的语义分数字段，应同步诊断 DTO 和入口文档。

预计达到修改文件不少于 3 个的实施阈值。确认实施后，应先在 `docs/AIChanges/Memory/` 创建唯一 `_plan.md`，并在独立执行对话中完成代码修改。

## 6. 风险与控制

1. clarity 全局提高可能让图过度发散：只提高初始核心人物边，不统一抬高所有边。
2. 实体命中权重过高可能造成关键词吸附：加入无关提及、否定表达和喫茶店话题反例。
3. 调整结构加分可能破坏既有玩家背景回忆：保留无明确实体时的原有优势，并跑现有路由 profile 测试。
4. 冷启动规则只影响新游戏生成的图；旧运行库若需迁移，应在实施 plan 中明确一次性迁移或要求重新开局，不能静默批量改历史边。
5. 不把话题实体加入图起点，继续遵守当前 Workstream 已确认的固定起点边界。

## 7. 验收标准

1. 九条莲以低 bond 初始化后仍清楚认识千早。
2. 问“你知道千早在哪里吗”时，图路径优先命中千早关系边，而非先取无关玩家背景。
3. 图中没有千早地点事实时，回答只能表达不知道或有限认知，不能凭检索修复制造位置事实。
4. 问喫茶店或玩家经历时，相关玩家背景仍能正常命中。
5. 现有对话记忆、夜间印象和路由 profile 测试不回退。
6. `aisc_debug` 能说明实际起点、选边、最终节点、是否兜底和失败原因。

