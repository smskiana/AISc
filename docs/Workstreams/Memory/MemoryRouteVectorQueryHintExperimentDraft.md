# 记忆路由单句向量查询提示实验草案

## 1. 文档定位

本文定义先使用 LongCat 验证“模型不再输出完整 `RetrievalDirection` JSON，只输出一行用于向量检索的普通语句”是否能显著降低方向生成延迟，并保持真实检索质量。

本文是实验草案，不是实施 plan，不授权修改当前 R3 v2 worker、provider chain、`memory_retrieval.yaml`、正式 Prompt、SQLite/LanceDB、Unity 对话流程或模型资产。进入实际实现前，必须在 `docs/AIChanges/Memory/` 创建唯一 plan，并按独立执行、独立测试会话完成。

2026-07-21 决策更新：A/B/C 报告已完成，用户选择 C。正式切换的唯一执行案为 [2026-07-21_记忆路由零LLM确定性查询切换_plan.md](../../AIChanges/Memory/2026-07-21_记忆路由零LLM确定性查询切换_plan.md)，实现记录见 [对应 execution](../../AIChanges/Memory/2026-07-21_记忆路由零LLM确定性查询切换_execution.md)，独立验收待 [对应 test](../../AIChanges/Memory/2026-07-21_记忆路由零LLM确定性查询切换_test.md)。生产默认已切为三 mode `local_only + [local]`，R3 v2 / LongCat 不再参与实时默认方向生成。

相关现状与证据：

1. [R3 v2 运行时接入草案](MemoryRouteR3V2RuntimeIntegrationDraft.md)。
2. [R3 v2 运行时接入 plan](../../AIChanges/Memory/2026-07-20_R3v2记忆路由运行时接入_plan.md)。
3. [R3 v2 运行时接入 execution](../../AIChanges/Memory/2026-07-20_R3v2记忆路由运行时接入_execution.md)。
4. [R3 v2 运行时接入 test](../../AIChanges/Memory/2026-07-20_R3v2记忆路由运行时接入_test.md)。
5. 2026-07-21 一次性尾延迟诊断：关闭 thinking 的 R3 v2 固定生成 84 tokens，5 次为 `9.905-12.363s`；Unity 真实检索出现 `14.718s` 成功和 `16.622/16.688s` timeout；开启 thinking 为 `42.504-46.262s` 且 5/5 非法 JSON；LongCat 完整方向 JSON 为 `5.186-12.196s`。

## 2. 问题定义

当前 R3 v2 同时生成以下完整方向字段：

```text
entity_mentions
location_mentions
themes
relation_facets
time_scope
source_preferences
recall_intent
negative_directions
retrieval_query
query_constraints
```

这些字段可以提供丰富的图路由语义，但也带来三个问题：

1. 确定性输出仍约 84 tokens，逐 token 解码成为主要延迟来源。
2. 模型必须维护完整 JSON、枚举和数组结构，生成时间被格式字符和可由本地规则推导的字段占用。
3. 玩家实时对话无法接受约 10-17 秒的检索等待；继续放宽 `16000ms` timeout 只会延长等待，不解决体验问题。

本草案验证一个更小的问题：模型是否只需要把当前问题和近期上下文压缩成一句更适合 BGE 的检索语句，而方向默认值、图搜索、权限和最终选择继续由本地代码处理。

## 3. 核心假设

### 3.1 待验证假设

LongCat 只输出一行短检索语句时：

1. 输出可以从完整 JSON 的数十至上百 tokens 降到约 8-24 tokens。
2. 总调用延迟相对现有完整方向 JSON 显著下降。
3. 单句包含当前人物、地点、时间或意图重点后，BGE 命中不低于当前 `retrieval_query`。
4. 本地图起点和深搜使用本地默认方向时，仍能保持 expected/forbidden 节点边界。

### 3.2 必须同时验证的反假设

现有 `retrieval_query.py` 已能用原问题和至多一条相关近期对白构造单次向量 query。模型生成的短句可能与确定性 query 等价，甚至因改写遗漏否定、人物纠正或时间词而更差。

因此实验必须包含“零 LLM 确定性 query”对照。如果单句模型方案不能稳定优于零 LLM 对照，就不应为了轻微语义改写保留一次模型调用。

## 4. 冻结边界

实验不得改变：

1. 每 NPC 独立图、SQLite 图层和 LanceDB/SQLite 向量层分工。
2. 图起点、权限、archived 过滤、clarity、副作用和最终重排规则。
3. 每次 `llm_guided_local` 最多一次向量查询的预算。
4. `local_only`、`llm_guided_local`、`llm_full_route` 三种公开策略。
5. NPC-NPC 和午夜默认 `local_only` 口径。
6. R3 v2 当前正式 Adapter、schema v1 和生产 provider chain。
7. LongCat `thinking.type=disabled`；不得用 `/no_think` system 文本代替官方请求字段。

单句不得成为节点 ID、边 ID、权限结论、最终记忆选择或图搜索指令。

## 5. 实验接口

### 5.1 模型输出

候选接口只表达一行普通语句：

```text
千早当前的位置或最近去向
```

模型不得输出：

1. JSON、Markdown fence、标签、解释、推理过程或多行文本。
2. 节点 ID、边 ID、存档 ID 或未从输入证明的人物/地点。
3. “应该检索”“请查询”等操作性前缀。
4. NPC 不应知道的私有事实。

Prompt 使用软约束要求一句话和建议长度，不给 LongCat 设置 `max_tokens` 硬上限，保持当前通用 LLM 调用口径。未来若为本地专项模型训练新 Adapter，可单独冻结较小的 generation 上限。

### 5.2 深 seam

建议实验接口：

```text
RetrievalQueryHintProvider.provide(request, context)
    -> RetrievalQueryHintResolution
```

`RetrievalQueryHintResolution` 只需包含：

```text
text
source
failure_reason
latency_ms
```

调用方不感知 LongCat Prompt、请求体、清洗规则或供应商响应。provider 的实现可以替换，接口保持稳定。

### 5.3 本地收口

建议由独立纯函数模块完成：

```text
ValidatedVectorQueryBuilder.build(request, context, hint_resolution)
    -> str
```

该模块隐藏以下行为：

1. 去除 fence、引号、标签和多余空白，只接受单行文本。
2. 执行字符数、控制字符、节点/边 ID 和未知 mention 校验。
3. 要求输出与原问题、参与者、当前位置、近期对白或已授权 alias 至少存在可证明语义来源。
4. 非法、空、超长或语义越权时回退到现有确定性 query。
5. 最终只产生一次 embedding query，不增加第二次 ANN。

三种及未来更多 hint provider 通过 provider registry 扩展，不在 `RetrievalEngine` 增长专项 `if/elif`。

## 6. 本地图方向

单句方案不再要求模型生成完整 `RetrievalDirection`。第一轮实验使用现有 `LocalDirectionProvider` 从原问题和上下文生成图方向；模型短句只替换向量 query 的语义文本。

正式检索候选流程为：

```text
RetrievalRequest
  -> LocalDirectionProvider
  -> 本地图起点与深搜
  -> RetrievalQueryHintProvider（实验组才调用）
  -> ValidatedVectorQueryBuilder
  -> 单次 BGE / ANN
  -> 现有最终重排与预算
```

这样可以把实验归因限定为“向量 query 是否更好”，避免同时改变图方向和向量文本后无法判断收益来源。

若实验发现单句缺少图方向会造成明显质量损失，应停止本方案，回到精简结构化意图，而不是让自然语言短句隐式承载不可校验的图路由指令。

## 7. LongCat 实验组

所有组使用同一输入、同一隔离图、同一 BGE、同一图预算和同一最终重排。

| 组 | 方向来源 | 向量 query | 目的 |
|---|---|---|---|
| A：完整 JSON 基线 | LongCat 完整 `RetrievalDirection` | 当前模型 `retrieval_query` 收口 | 记录现有通用方向质量、tokens 和延迟 |
| B：单句 hint | `LocalDirectionProvider` | LongCat 一行短句，经本地校验 | 验证极短输出的延迟与检索质量 |
| C：零 LLM | `LocalDirectionProvider` | 现有确定性 query | 判断模型改写是否值得一次网络/模型调用 |

不得把 R3 v2 当前 JSON Adapter 直接改 Prompt 后冒充 B 组。R3 v2 是按 schema v1 完整 JSON 训练的；单句方案若通过 LongCat 验证，后续必须用新数据和新 Adapter 独立训练。

## 8. 数据集与顺序

### 8.1 第一阶段：契约 smoke

1. 从已批准、脱敏、`contains_real_session_data=false` 的数据中选 4 条。
2. 至少覆盖明确人物定位、人物否定纠正、时间范围变化和无明确实体的一般回忆。
3. A/B 各调用一次，C 不调用模型。
4. 任一 B 输出出现多行、解释、越权 mention 或无法形成安全 query，先停止扩大样本。

### 8.2 第二阶段：冻结质量集

使用现有 12 条冻结 test，对 A/B/C 逐条比较：

1. expected/forbidden 节点。
2. 明确人物和地点召回。
3. 否定纠正、stale location 和时间范围。
4. 向量 query 与最终条目的可解释一致性。
5. 模型输出字符数、token 数和合法率。

### 8.3 第三阶段：延迟重复

从 12 条中选 4 条代表性输入，每条 A/B 各重复 5 次。按样本交错和随机顺序调用，避免把供应商时段抖动误判为 Prompt 收益。

分别记录：

1. Prompt tokens。
2. Completion tokens。
3. 首 token 延迟；若当前兼容接口无法提供，明确记为未覆盖。
4. 完整响应墙钟。
5. 本地校验、embedding、ANN 和端到端 probe 墙钟。

## 9. 验收标准

### 9.1 安全与格式

1. B 组 12/12 为单行普通语句。
2. 未知实体、地点、节点 ID、边 ID 和权限越界为 0。
3. 非法输出 100% 确定性回退，不增加第二次模型调用或向量查询。

### 9.2 检索质量

1. B 组 expected node 命中不低于 A 组和 C 组中的较高者。
2. B 组 forbidden node 命中为 0。
3. 明确实体召回、否定纠正、当前/最近/历史时间口径不得低于冻结基线。
4. 若 B 只优于 A、但不优于 C，则判定“压缩有效、模型无必要”，优先采用 C。

### 9.3 性能

1. B 组 completion token p95 不高于 24。
2. B 组相对 A 组 completion token 至少减少 65%。
3. B 组 LongCat 成对墙钟 p50 至少降低 30%，p95 不得恶化。
4. B 组端到端 probe p95 必须低于 5 秒，才有资格进入本地专项模型验证。
5. C 组若质量达标且端到端显著快于 B，直接停止模型路线并选择 C。

LongCat 通过不等于本地 Qwen 延迟通过。它只证明短文本任务具有足够语义和更小输出；本地专项模型仍需单独达到 Unity 实际对话 p50 不高于 3 秒、p95 不高于 5 秒。

## 10. 停止条件

出现以下任一情况，不进入 R3 单句 Adapter 训练：

1. B 组检索质量低于 C 组。
2. B 组经常复述问题而没有提供可衡量的向量收益。
3. B 组遗漏否定、人物纠正或时间词，导致 forbidden 命中。
4. B 组 p95 仍高于 5 秒。
5. 短句需要重新塞入大量结构说明或 few-shot 才能稳定，导致 Prompt 和延迟收益消失。
6. 只能依赖不可校验的自然语言暗示恢复图方向质量。

## 11. 诊断与隐私

结构化报告可以保存：

```text
sample_id
variant
prompt_tokens
completion_tokens
hint_char_count
hint_validation_status
fallback_reason
provider_latency_ms
embedding_ms
ann_ms
probe_elapsed_ms
expected_hit_count
forbidden_hit_count
```

报告不得保存真实玩家对白、完整 Prompt、完整记忆文本、API key 或供应商原始响应。实验只使用已批准脱敏数据；原始报告写入 `F:/AIScLocalArtifacts/memory-route/artifacts/`，仓库文档只记录摘要、路径和 SHA-256。

## 12. 预期实验产物

若用户批准实施，后续 plan 应限定为实验工具和隔离数据，不修改生产 provider：

1. 一个 LongCat A/B/C 评估入口。
2. 一个窄的临时 `RetrievalQueryHintProvider` fake/adapter seam。
3. 一个纯函数 `ValidatedVectorQueryBuilder` 或等价实验实现。
4. 结构化质量、tokens、延迟和检索报告。
5. 是否进入新 Adapter 训练的明确结论。

实验通过后再单独制定本地模型 plan，冻结新的单句 schema、训练数据、Adapter 身份、worker generation 上限、provider ID、兼容和回退方案。不得在 LongCat 实验执行会话顺手改造 R3 v2 生产实现。

## 13. 当前建议

优先执行 A/B/C 小规模 smoke。最重要的决策不是“如何让模型少输出 JSON”，而是“向量 query 是否还需要模型”。

推荐顺序：

```text
先证明 B 比 A 更快且质量不降
  -> 再证明 B 确实优于 C
    -> 才训练新的本地单句 Adapter
```

如果 C 已达到同等质量，应直接使用零 LLM 确定性 query，把实时对话的方向生成延迟降为本地规则和一次 embedding 成本。
