# 记忆路由专项模型切换草案

## 1. 文档定位

本文定义把现有 `memory_direction` 通用 LLM 调用切换为本地专项模型的验证路线、运行时边界和回退契约。

本文是方案草案，不是实施 plan，不授权修改代码、配置、模型资产或当前生产路由。实际实施前必须在 `docs/AIChanges/Memory/` 创建唯一 plan，并在独立执行会话中引用该 plan。

## 2. 目标

1. 先在 Python 后端验证专项模型是否能稳定替代通用 LLM 的方向解析能力。
2. 保持 `RetrievalEngine.retrieve(request)` 对调用者的现有单一接口。
3. 保持当前图起点、知识权限、本地实体校准、向量查询次数、深搜预算和最终重排口径不变。
4. 专项模型失败、超时、非法输出或低置信度时，继续通过稳定回退完成基础检索。
5. Python 验证通过后，再把已冻结的输入输出契约迁移到 C#；迁移不能反向改变模型任务语义。

## 3. 非目标

1. 不让专项模型读取或生成节点 ID、边 ID、存档 ID。
2. 不让专项模型直接执行图搜索、向量搜索或最终记忆选择。
3. 不用专项模型替代 embedding 模型。
4. 不改变 `local_only`、`llm_guided_local`、`llm_full_route` 三种公开检索策略。
5. 不在本草案中决定 Python 后端整体移除方案。
6. 不因模型输出结构合法就跳过现有语义校准和权限过滤。

## 4. 当前边界

当前 `memory_direction` 使用当前发言、会话摘要、近期对白、近期记忆、地点、时间和参与者生成 `RetrievalDirection`。本地代码随后负责：

1. 清理非法枚举和超长字段。
2. 保留玩家明确提及的实体。
3. 校准未知人物、地点、时间和来源偏好。
4. 生成至多一次 embedding / ANN 使用的 `retrieval_query`。
5. 按 mode policy 执行本地图搜索、向量锚点和最终原子条目选择。

专项模型只替换第一步的方向建议来源，不接管后续权威判断。

## 5. 首轮模型候选

| 角色 | 候选 | 用途 |
|---|---|---|
| 首选专项模型 | `Qwen3-0.6B` + Route LoRA | 验证低资源本地路由上限 |
| 尺寸对照 | `Qwen3-1.7B` + Route LoRA | 判断复杂指代和隐含关系收益 |
| 现状基线 | 当前通用 LLM `memory_direction` | 教师、质量上限和回归基准 |
| 本地基线 | `LocalDirectionProvider` | 无模型回退和最低可用基准 |

首轮只做监督微调，不引入 DPO 或强化学习。底模仓库、revision、tokenizer、许可证快照、训练框架版本和量化格式必须在实施 plan 中锁定，不能只记录营销名称。

## 6. 稳定输入契约

Python 验证和未来 C# 推理必须使用同一份规范化输入 DTO，至少包含：

```text
schema_version
query_text
conversation_summary
recent_turns[]
recent_memories[]
location_id / location_display_text
game_time_snapshot
participant_ids[]
known_entity_aliases[]
mode
```

约束：

1. `query_text` 是当前问题的原文，不得被摘要替代。
2. 近期对白和近期记忆使用固定数量与字符预算，训练和推理一致。
3. 中文内容通过 JSON 或 UTF-8 文件输入测试脚本，避免 Windows CLI 参数转码。
4. 稳定 ID 与显示文本分离；模型可以看显示文本，但结果必须由本地 resolver 映射为稳定实体。
5. 不把全图节点、边或未经权限过滤的其他 NPC 记忆塞入模型上下文。

## 7. 稳定输出契约

专项模型继续输出现有 `RetrievalDirection` 语义：

```json
{
  "entity_mentions": [],
  "location_mentions": [],
  "themes": ["general"],
  "relation_facets": [],
  "time_scope": "any",
  "source_preferences": [],
  "recall_intent": "general_recall",
  "negative_directions": [],
  "retrieval_query": "",
  "query_constraints": [],
  "confidence": 0.0
}
```

`confidence` 是专项模型 provider 的新增诊断建议值，不直接成为业务事实。实施时若加入正式 DTO，必须同时更新 Python、诊断协议和未来 C# DTO；若不希望扩大稳定协议，可只保存在 provider 内部 trace。

输出约束：

1. 使用 JSON Schema 或 grammar 约束解码，禁止自由格式回答。
2. 枚举字段只能取当前代码允许值。
3. `retrieval_query` 不得引入当前问题、近期对白和已授权上下文之外的新人物、地点、时间或事件。
4. 明确实体以本地提取结果为权威；模型只能补充候选，不能删除或改写明确实体。
5. 输出不得包含推理过程、节点 ID、边 ID或给最终对话模型的回答文本。

## 8. Provider 切换设计

方向来源建议收敛为统一 provider 接口：

```text
DirectionProvider.provide(request, context) -> DirectionResolution
```

可配置 provider：

```text
local
general_llm
specialist_python
specialist_csharp   # 未来保留位，本轮不实现
```

建议的模式配置：

```yaml
direction_provider: specialist_python
fallback_chain:
  - general_llm
  - local
shadow_provider: general_llm
specialist:
  model_id: qwen3_0_6b_route
  schema_version: 1
  confidence_threshold: 0.80
  timeout_ms: 1500
```

真实字段名应在实施时复用现有配置结构，不因示例机械新增平行配置系统。

切换要求：

1. provider 选择在单次请求开始时冻结，处理中途不得切换。
2. 模型加载失败不能阻止后端启动；对应策略必须明确降级并记录原因。
3. 配置修改是否热加载沿用当前 memory policy 口径；若仍需重启，应明确显示生效状态。
4. shadow provider 只产出诊断，不影响正式检索结果，也不得重复执行 ANN。

## 9. Python 验证阶段

### 9.1 数据采集

每条样本至少记录：

1. 规范化输入 DTO。
2. 当前通用 LLM 原始输出。
3. 本地清洗和校准后的方向。
4. 实际向量 query。
5. 图候选、向量候选和最终节点。
6. 人工或固定夹具定义的期望相关节点。
7. 回答阶段是否出现无证据实体或遗漏明确实体。

禁止把通用 LLM 原始输出未经校验直接当作金标。结构合法但语义错误的方向必须修正或排除。

### 9.2 数据覆盖

训练与评估至少覆盖：

1. 明确人物、地点、事件和时间。
2. 代词、省略主语和跨轮指代。
3. 否定、纠正、反问和比较。
4. 多人物竞争、多地点同名和别名。
5. 无相关记忆、无权知道和错误前提。
6. 当前场景噪声与真正回忆目标冲突。
7. `player_dialogue`、`npc_dialogue` 与受控夜间方向的边界。

训练集、验证集和测试集应按剧情主题、人物组合或会话来源分组切分，不能随机拆散同一对话的相邻样本。

### 9.3 训练矩阵

首轮最小矩阵：

| 实验 | 模型 | 训练 |
|---|---|---|
| R0 | 本地 provider | 无 |
| R1 | 当前通用 LLM | 无 |
| R2 | Qwen3-0.6B | zero-shot / few-shot |
| R3 | Qwen3-0.6B | Route LoRA SFT |
| R4 | Qwen3-1.7B | Route LoRA SFT |

统一使用确定性解码；若框架允许 thinking，路由推理必须关闭 thinking。

## 10. 评估与门禁

### 10.1 字段级指标

1. 明确实体召回率。
2. 未知实体产生率。
3. 枚举字段 Macro-F1。
4. JSON/schema 合法率。
5. `retrieval_query` 新事实和新实体违规率。

### 10.2 检索级指标

1. 期望节点 Recall@K。
2. 最终记忆命中率。
3. 无权知识泄露率。
4. 最终回答的无证据断言率。
5. 与当前通用 LLM 基线的质量保持率。

### 10.3 性能指标

1. 冷启动加载时间。
2. 单请求 p50 / p95 / p99。
3. 峰值内存和常驻内存。
4. 超时、非法输出和回退比例。
5. 每轮 embedding / ANN 次数仍不超过当前预算。

建议初始通过线：

1. JSON/schema 合法率不低于 `99.9%`。
2. 明确实体召回率不低于当前通用 LLM + 本地校准链路。
3. 未知实体和知识越权不得高于当前基线。
4. 最终相关记忆命中率达到当前通用 LLM 基线的 `95%` 以上。
5. 失败样本全部走稳定回退，不产生空检索或异常中断。

具体阈值必须由真实数据基线确认后写入实施 plan，以上只作为首轮实验目标。

## 11. 切换阶段

### 阶段 A：离线重放

专项模型只读取固定样本，不接入正式对话。通过字段级和检索级离线评估后才能进入 shadow。

### 阶段 B：在线 shadow

正式结果继续使用当前 provider；专项模型并行生成方向，只记录差异、延迟和如果采用该方向将命中的候选。shadow 不写记忆、不恢复 clarity、不重复执行正式 ANN。

### 阶段 C：开发环境主路由

专项模型成为开发环境方向来源，通用 LLM 和本地 provider 组成回退链。出现超时、非法 JSON、低置信度、未知实体或校准失败时立即回退。

### 阶段 D：默认切换

只有长测、真实图竞争测试和故障注入通过后，才能把专项模型设为默认。通用 LLM 回退的移除必须单独决策，不能和默认切换同时发生。

### 阶段 E：C# 迁移

冻结 tokenizer、模型 revision、输入模板、JSON Schema、量化方式和 golden corpus。C# 实现必须先通过 Python/C# 同输入对照，再接管正式 provider。

## 12. 回退与诊断

稳定失败原因建议至少区分：

```text
specialist_unavailable
specialist_load_failed
specialist_timeout
specialist_invalid_json
specialist_schema_invalid
specialist_low_confidence
specialist_semantic_rejected
specialist_fallback_general_llm
specialist_fallback_local
```

诊断至少记录模型 ID、revision、adapter ID、schema version、输入长度、输出摘要、推理耗时、校准错误、回退来源和最终采用的 provider。不得在发行日志中泄露完整玩家对白或未授权记忆内容。

## 13. 与融合专项模型的关系

路由与融合首轮使用独立 Adapter，避免任务干扰和实验归因不清。路由专项模型通过后，再与融合专项模型共同评估 `Qwen3-1.7B + multitask adapter`：

1. 使用显式 `<TASK_ROUTE>` / `<TASK_MERGE>` 任务标记。
2. 两个任务分别保留独立测试集。
3. 多任务模型只有在两个任务均达到独立 Adapter 指标的 `97%` 以上时，才成为统一运行时候选。
4. 统一模型是部署优化，不得以牺牲事实安全换取少加载一个模型。

## 14. 实施边界与风险

1. `RetrievalEngine` 已是稳定 facade，专项 provider 不应继续塞入该类；模型加载、推理和 schema 解析必须有独立职责边界。
2. 如实施会继续扩大现有过重类，必须先取得用户“减重并执行”授权。
3. 专项模型训练数据会继承教师模型偏差，必须保留人工校正和困难负样本。
4. 模型量化可能改变枚举、JSON 和指代行为，量化产物必须单独验收。
5. Python 通过不等于 C# 通过；tokenizer、模板或采样参数任一差异都可能改变输出。

## 15. 实施前验收标准

进入实际实施 plan 前，至少应确认：

1. 首轮底模、许可证与可分发性。
2. 路由 golden corpus 的来源和人工复核方式。
3. Python 推理框架、硬件预算和模型缓存位置。
4. shadow 模式不会增加 ANN 次数或改变正式结果。
5. C# 迁移目标平台和可接受的内存、包体、冷启动预算。

## 16. 相关入口

1. `docs/Workstreams/Memory/README.md`
2. `docs/Workstreams/Memory/LlmGuidedLocalDeepRetrievalDraft.md`
3. `docs/Workstreams/Memory/LlmRetrievalQueryVectorRoutingFixDraft.md`
4. `docs/DecisionRecords/ADR-0001-memory-v07-light-graph.md`
5. `backend/src/memory/retrieval_contracts.py`
6. `backend/src/memory/retrieval_direction.py`

