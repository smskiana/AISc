# 记忆融合专项模型切换草案

## 1. 文档定位

本文定义把现有 `memory_merge` 通用 LLM 文本生成切换为本地专项模型的验证路线、安全契约和回退机制，并说明它与概率化节点融合方案的边界。

本文是方案草案，不是实施 plan，不授权修改当前融合代码、概率公式、数据库、Prompt 或模型资产。实际实施前必须在 `docs/AIChanges/Memory/` 创建唯一 plan，并在独立执行会话中引用该 plan。

## 2. 目标

1. 先用 Python 验证专项模型能否在不产生新事实的前提下完成语义融合与受控模糊化。
2. 把“是否选择候选”“如何生成融合文本”“是否提交图变更”拆成可独立验证的职责。
3. 融合模型输出必须结构化、可校验、可拒绝和可追溯。
4. 模型失败或结果不可信时跳过本次融合，绝不以自由文本 fallback 强行提交。
5. Python 验证通过后，再冻结契约迁移 C#，不在 C# 阶段重新定义融合语义。

## 3. 非目标

1. 不让模型计算 `merge_likelihood`、`merge_probability` 或执行随机抽签。
2. 不让模型选择任意图节点、读写数据库、继承边或归档来源节点。
3. 不扩大 ADR-0001 的轻量图模型。
4. 不把融合模型当作事实补全或世界知识生成器。
5. 不用专项模型替代 embedding、相似度计算或权限过滤。
6. 不在本草案中提前启用概率化融合；该功能仍受 Memory Workstream 的排期和前置条件约束。

## 4. 当前问题

当前 `_merging()` 同时承担候选收集、相似度筛选、Prompt 调用、融合文本接收、向量写入、边继承、来源记录和旧节点归档。模型只返回一段自由文本，系统无法直接判断：

1. 哪些来源事实被保留。
2. 是否引入了来源中不存在的新人物、地点、时间、因果或关系。
3. 两条记忆是否冲突或根本不应融合。
4. 输出是明确语义融合还是低确定性的混淆记忆。
5. 模型低置信度时是否应跳过。

专项模型切换必须先建立结构化结果和提交前验证，不得只替换模型地址。

## 5. 职责拆分

建议的稳定流程：

```text
确定性候选构建
-> 确定性年龄 / clarity / similarity / 权限门禁
-> 确定性概率抽签
-> SpecialistMergeProvider 生成 MergeProposal
-> MergeProposalValidator 校验来源事实、冲突和模式约束
-> 事务性提交新节点、继承边、来源记录和归档
```

职责边界：

| 职责 | 权威来源 |
|---|---|
| 候选池、预算、是否参与抽签 | 本地代码 |
| `semantic_merge` / `confusion_merge` 请求模式 | 本地代码 |
| 来源节点与权限 | 本地数据库 |
| 事实抽取、冲突提示、融合表述 | 专项模型建议 |
| 输出是否合法、是否允许提交 | 本地 validator |
| 图边继承、归档和事务 | 本地代码 |

## 6. 首轮模型候选

| 角色 | 候选 | 用途 |
|---|---|---|
| 首选专项模型 | `Qwen3-1.7B` + Merge LoRA | 事实保持、冲突识别、受控改写 |
| 尺寸对照 | `Qwen3-0.6B` + Merge LoRA | 判断更低资源模型是否足够 |
| 现状基线 | 当前通用 LLM `memory_merge` | 教师和质量对照 |
| 安全基线 | 直接跳过融合 | 零模型风险和故障回退 |

融合任务首轮只做监督微调。若专项模型仍存在系统性事实污染，应先改数据和输出契约，不用偏好训练掩盖接口问题。

## 7. 稳定输入契约

建议定义 `MergeSpecialistRequest`：

```json
{
  "schema_version": 1,
  "merge_mode": "semantic_merge",
  "observer_id": "npc_id",
  "source_memories": [
    {
      "source_id": "opaque_source_1",
      "memory_type": "event",
      "value": "...",
      "created_day": 12,
      "clarity": 0.52
    },
    {
      "source_id": "opaque_source_2",
      "memory_type": "event",
      "value": "...",
      "created_day": 18,
      "clarity": 0.49
    }
  ],
  "allowed_entities": [],
  "forbidden_assertion_types": [],
  "max_output_chars": 240
}
```

约束：

1. 第一阶段只允许两条同类型 `event` 来源，沿用当前工程边界。
2. `source_id` 只用于结果对应，不把真实图结构暴露给模型；未来可改为请求内序号。
3. `allowed_entities` 由本地从来源和已授权别名解析，不由模型扩展。
4. `semantic_merge` 与 `confusion_merge` 使用同一 DTO，但约束不同。
5. 不向模型注入其他 NPC 私密记忆或全局事实用于“补全”。

## 8. 稳定输出契约

建议定义 `MergeProposal`：

```json
{
  "decision": "merge",
  "merge_mode": "semantic_merge",
  "preserved_facts": [
    {
      "fact": "...",
      "source_refs": ["opaque_source_1", "opaque_source_2"]
    }
  ],
  "conflicts": [],
  "uncertainties": [],
  "merged_memory": "...",
  "confidence": 0.0
}
```

允许的 `decision`：

```text
merge
skip
```

允许的 `merge_mode`：

```text
semantic_merge
confusion_merge
none
```

本地请求模式是权威。模型不能把 `confusion_merge` 升格为 `semantic_merge`；模型认为不安全时可以返回 `skip`。

## 9. 两种融合模式

### 9.1 semantic_merge

目标是概括两条语义接近的事件，同时保持共同事实和必要差异。

硬约束：

1. 不新增来源中不存在的人物、地点、时间、行为、因果或关系。
2. 不把可能、听说、猜测改成确定事实。
3. 来源冲突无法安全表达时返回 `skip`。
4. 不为了流畅而删除会改变事件含义的限定词。

### 9.2 confusion_merge

目标是表达旧且模糊记忆的混合印象，不生成新的确定事实。

硬约束：

1. 不断言精确时间、精确地点、具体因果或新关系。
2. 使用明确的不确定表达，但不凭空增加情绪或评价。
3. `preserved_facts` 只列仍被输出安全保留的事实。
4. 无法在不制造错误事实的情况下模糊化时返回 `skip`。

## 10. 提交前验证

`MergeProposalValidator` 应至少检查：

1. JSON Schema、枚举、字段长度和数量。
2. 模型输出的实体是否都在 `allowed_entities` 中。
3. `source_refs` 是否只引用本次输入。
4. `merge_mode` 是否与本地请求一致。
5. `semantic_merge` 是否保留关键主语、对象、否定和不确定性。
6. `confusion_merge` 是否出现禁止的精确时间、地点、因果或关系断言。
7. `decision=skip` 时 `merged_memory` 必须为空。
8. 低置信度、事实冲突未解释或 validator 无法判断时一律拒绝提交。

validator 第一版可以组合确定性规则、实体白名单和离线教师评审。运行时不得为了让更多样本通过而调用另一个不可控生成模型兜底。

## 11. Provider 切换设计

建议收敛为：

```text
MergeProvider.propose(request) -> MergeProposal
```

可配置 provider：

```text
general_llm
specialist_python
specialist_csharp   # 未来保留位，本轮不实现
disabled
```

建议配置示例：

```yaml
merge_provider: specialist_python
failure_policy: skip
shadow_provider: general_llm
specialist:
  model_id: qwen3_1_7b_merge
  schema_version: 1
  confidence_threshold: 0.90
  timeout_ms: 3000
```

与路由不同，融合失败不应自动调用通用 LLM 并提交结果。默认 `failure_policy` 必须是 `skip`，因为融合属于不可逆的持久数据演化，错误输出会污染后续检索和存档。

## 12. Python 验证数据

### 12.1 样本来源

1. 当前真实运行图中的融合候选与来源记录。
2. 现有通用 LLM 生成结果，但必须经过人工或规则复核。
3. 人工构造的冲突、否定、信息不对称和不应融合样本。
4. 概率化融合草案需要的低相似度、低 clarity、旧记忆样本。
5. 对现有安全样本进行实体、时间、地点和否定扰动生成困难负样本。

### 12.2 必须覆盖的类别

1. 同一事件的不同表述。
2. 同一人物的不同事件。
3. 相似地点但不同主体。
4. 时间冲突、地点冲突和行为冲突。
5. 否定与肯定冲突。
6. 传闻、猜测和亲历事实的来源强度差异。
7. 私密事实与观察者无权知识。
8. `semantic_merge` 应成功样本。
9. `confusion_merge` 应模糊化样本。
10. 两种模式都应 `skip` 的样本。

训练集、验证集和测试集按人物组合、剧情事件族或来源图分组切分，避免同一事实改写泄漏到测试集。

## 13. 训练矩阵

首轮最小矩阵：

| 实验 | 模型 | 训练 |
|---|---|---|
| M0 | 当前通用 LLM | 现有 Prompt |
| M1 | Qwen3-0.6B | zero-shot / few-shot |
| M2 | Qwen3-0.6B | Merge LoRA SFT |
| M3 | Qwen3-1.7B | Merge LoRA SFT |
| M4 | 禁用模型 | 全部 skip 安全基线 |

统一使用确定性或近确定性解码。现有 `temperature=0.5` 不应机械迁移到专项模型；融合专项模型第一版建议 `temperature=0`，通过训练样本表达模式差异。

## 14. 评估与硬门禁

### 14.1 事实安全

1. 新实体产生率。
2. 新事实产生率。
3. 否定翻转率。
4. 不确定性确定化率。
5. 冲突遗漏率。
6. 无权知识泄露率。

这些指标是硬门禁。任何系统性事实污染都优先修正数据、contract 或 validator，不用平均文本分数抵消。

### 14.2 融合质量

1. 来源关键事实保留率。
2. `merge` / `skip` 决策准确率。
3. `semantic_merge` 与 `confusion_merge` 模式服从率。
4. 字符压缩比例。
5. 表述可读性和观察者视角一致性。
6. 融合后相关问题的检索 Recall@K。

### 14.3 长期影响

1. 融合节点是否仍可通过继承边到达。
2. 旧节点归档后强制回忆是否可追溯来源。
3. 多次融合后事实漂移是否累积。
4. 融合后的 embedding 是否错误吸引不相关查询。
5. 保存、加载和午夜部分失败时是否保持原子性。

建议初始通过线：

1. 新实体、新确定事实、知识越权和否定翻转在人工金标集上为 `0`。
2. 应 `skip` 样本的召回率不低于 `99%`。
3. 来源关键事实保留率不低于当前通用 LLM 基线。
4. 融合后检索命中率不低于融合前来源节点可用时的可接受下限。
5. 模型或 validator 失败时不产生任何数据库写入。

具体数值必须用真实图建立基线后写入实施 plan。

## 15. 切换阶段

### 阶段 A：离线生成

专项模型只处理固定样本，不接触正式数据库。比较自由文本基线、结构化专项输出和人工金标。

### 阶段 B：真实候选 shadow

午夜流程照常使用当前正式融合或临时禁用写入；专项模型对真实候选生成 proposal，只记录差异。shadow 结果不得创建节点、继承边、归档来源或恢复 clarity。

### 阶段 C：开发存档受控写入

仅在可重建的测试存档中允许专项模型结果通过 validator 后提交。每次提交记录完整来源、模型 revision、adapter、schema、proposal 摘要和 validator 结果。

### 阶段 D：默认切换

专项模型、validator、事务提交和长测全部通过后，才能设为默认。通用 LLM 不作为自动提交 fallback；故障时跳过融合并报告。

### 阶段 E：C# 迁移

冻结 tokenizer、模型 revision、Adapter、输入模板、JSON Schema、量化格式、validator 规则和 golden corpus。C# 必须先复现 Python proposal 与验证结论，再接管正式融合 provider。

## 16. 事务与失败策略

1. 模型推理发生在数据库提交事务之前。
2. validator 通过后，创建融合节点、写向量、继承边、写来源、删除旧图节点和归档旧向量必须作为一个可恢复的业务事务处理。
3. 任一步失败不得留下只有新节点、没有来源，或旧节点已退场、新节点未完成的半状态。
4. 模型超时、非法 JSON、低置信度或安全拒绝只记为“本轮跳过”，不伪装成功。
5. shadow 和评估模式不得修改随机抽签状态，避免观察行为改变正式融合选择。

## 17. 诊断

稳定失败原因建议至少区分：

```text
merge_specialist_unavailable
merge_specialist_load_failed
merge_specialist_timeout
merge_specialist_invalid_json
merge_specialist_schema_invalid
merge_specialist_low_confidence
merge_specialist_fact_rejected
merge_specialist_mode_rejected
merge_specialist_skip
merge_commit_failed
```

诊断至少记录：

1. 候选来源 ID、类型、年龄、clarity 和 similarity。
2. 本地请求的 `merge_mode`。
3. 模型 ID、revision、adapter 和 schema version。
4. proposal 摘要、validator 拒绝原因和推理耗时。
5. 是否提交、继承边数、归档来源数和事务终态。

发行日志不得输出未授权的完整私密记忆文本。

## 18. 与路由专项模型的关系

首轮保持独立：

```text
Qwen3-0.6B + Route LoRA
Qwen3-1.7B + Merge LoRA
```

独立实验通过后，可测试：

```text
Qwen3-1.7B + Multitask LoRA
```

多任务实验要求：

1. 使用显式任务标记和不同 JSON Schema。
2. 路由与融合分别统计指标，不用平均分掩盖融合安全回退。
3. 两个任务均达到独立 Adapter 指标的 `97%` 以上，且融合全部硬门禁不回退时，才考虑统一。
4. 若共享 Adapter 导致事实污染，即使节省内存也不得采用。

## 19. 实施边界与类减重

当前 `_merging()` 已同时包含候选、LLM、持久化和图变更职责。实际实施结构化 provider 和 validator 时会继续增加职责，已触发类减重要求。实施前必须取得用户“减重并执行”授权，并至少拆出：

1. 候选与概率策略。
2. `MergeProvider`。
3. `MergeProposalValidator`。
4. 事务性提交器。

不得把新的模型加载、schema 解析、事实验证和诊断分支继续塞入 `_merging()`。

## 20. 实施前验收标准

进入实际实施 plan 前，至少应确认：

1. 首轮底模、许可证、训练框架和可分发性。
2. `semantic_merge` / `confusion_merge` 金标规则。
3. 事实安全人工复核流程和困难负样本来源。
4. shadow 模式不写数据库、不影响抽签和正式结果。
5. 失败时 `skip` 的产品语义可接受。
6. 与概率化节点融合草案的排期关系和前置条件仍成立。

## 21. 相关入口

1. `docs/Workstreams/Memory/README.md`
2. `docs/DecisionRecords/ADR-0001-memory-v07-light-graph.md`
3. `backend/src/memory/evolution.py`
4. `backend/src/memory/embedding.py`
5. `backend/src/database/sqlite_client.py`
6. `memory_merge_sources`

