# LLM 浅层定向与本地图深层检索草案

## 1. 状态与范围

本文是需求与设计来源，不直接作为实施 plan。唯一执行案已创建：[`2026-07-17_LLM定向本地深层记忆检索_plan.md`](../../AIChanges/Memory/2026-07-17_LLM定向本地深层记忆检索_plan.md)。后续必须在独立执行对话中引用该 plan，并先取得“减重并执行”授权。

执行案已在本草案基础上扩展为三种可配置策略：`local_only`、`llm_guided_local`、`llm_full_route`。三种策略同时适用于玩家对话、NPC-NPC 和夜间印象；默认分别为玩家引导深搜、NPC-NPC 完全本地、夜间引导深搜，且夜间使用更高的深度、广度与输入数据预算。本文后续“第一阶段只改玩家”“每轮只调用一次 LLM”等原始草案表述，仅描述 `llm_guided_local` 的来源设想；与执行案冲突时以唯一 plan 为准。

本草案只解决一个方向：玩家对话时，先由 LLM 一次性理解回忆大方向，再由本地算法沿该方向执行稳定、可解释的深层图搜索。

本草案假定相关事实已经存在于当前 NPC 的图或向量层中。冷启动图内容不全、他人记忆如何衍生，见 `InitialKnowledgeProjectionDraft.md`。

## 2. 当前问题

当前玩家对话检索的主要流程是：

```text
固定起点 self + 当前对话对象
→ 本地对邻边做字符、实体、clarity 和结构打分
→ 本地足够确定则直接选边
→ 否则让 LLM 从本地候选边中逐跳选择
→ 最多两跳
→ 图结果不足时使用向量兜底
```

当前 `player_dialogue` 默认约束为每跳最多 6 条候选、选择 2 条边、最多 2 跳、最终 5 条记忆。它可以处理明确人名，但存在以下限制：

1. LLM 只能看到已经被本地 Top-N 截断的候选，正确方向若提前被淘汰，LLM 无法恢复。
2. LLM 在逐跳阶段承担节点选择，调用次数、延迟和随机性随跳数增加。
3. 本地普通语义仍以轻量字符重合为主，难以理解代词、描述性称呼、因果追问和关系问题。
4. 向量检索只在图结果不足时补最终节点，没有作为“发现深搜锚点”的统一能力。
5. 当前诊断能看到最终起点、选边和节点，但不能清楚区分“方向理解错”“图路径被截断”和“图内根本无事实”。

## 3. 目标与非目标

### 3.1 目标

1. LLM 只调用一次，负责识别用户希望回忆的大方向。
2. 本地算法负责多跳搜索、候选扩张、路径评分、权限过滤和预算控制。
3. 搜索深度不再等于固定的两跳，而是按方向、路径质量和预算自适应终止。
4. 向量检索既可补充图外结果，也可提供受控的语义锚点。
5. 每次检索都能解释方向、锚点、路径、淘汰原因和停止原因。
6. 对调用者继续保持单一 `RetrievalEngine.retrieve(request)` 接口。

### 3.2 非目标

1. 不让 LLM 直接生成数据库节点 ID 或任意边类型。
2. 不把完整图数据发送给 LLM。
3. 不让 LLM 生成缺失的记忆事实。
4. 不在本草案中补齐冷启动知识。
5. 不自动改变 NPC-NPC 与夜间印象检索口径；第一阶段只针对 `player_dialogue` 验证。
6. 不改变 ADR-0001 的轻量图 + 向量层边界。

## 4. 目标流程

```text
玩家当前发言 + 近期对白 + 会话摘要
→ LLM 生成受约束的 RetrievalDirection
→ 本地校验并解析稳定实体 / 地点 / 时间 / 关系维度
→ 建立固定起点与语义锚点
→ 本地图算法执行受预算控制的深层 beam search
→ 必要时用向量检索补充锚点或图外候选
→ 路径级重排、权限过滤和去重
→ 返回记忆上下文与完整诊断
```

LLM 只负责“往哪个方向想”，本地算法负责“沿图走多远、走哪条路径、哪些内容有权返回”。

## 5. LLM 浅层检索方向

### 5.1 输出契约

建议定义内部 DTO `RetrievalDirection`，第一版字段控制在稳定、可校验的范围：

```json
{
  "entity_mentions": ["千早"],
  "location_mentions": [],
  "themes": ["当前位置", "近期活动"],
  "relation_facets": ["认识程度", "职业"],
  "time_scope": "recent",
  "source_preferences": ["direct", "heard"],
  "recall_intent": "locate_person",
  "negative_directions": ["unrelated_player_background"]
}
```

LLM 输出只允许使用受控枚举和原文 mention：

1. mention 必须再次通过本地实体目录解析为稳定 ID。
2. 无法解析的 mention 只作为语义文本，不得成为数据库 ID。
3. `themes`、`relation_facets`、`time_scope`、`source_preferences`、`recall_intent` 必须有白名单。
4. LLM 输出非法、超时或解析失败时，回退到本地确定性方向提取，不中断对话。

### 5.2 LLM 不负责的内容

1. 不选择候选边序号。
2. 不决定最终节点。
3. 不判断 NPC 是否有权知道秘密。
4. 不补写图中不存在的事实。
5. 不直接给出回答文本。

## 6. 本地深层检索

### 6.1 起点与锚点

继续保留当前固定起点：

1. 当前 NPC 的 `self`。
2. 当前对话对象的 `person` 节点。

另外允许检索器内部建立“语义锚点候选”，但锚点不等于无条件图起点：

1. LLM mention 经本地目录解析出的实体节点。
2. 当前地点对应节点或相关元数据命中节点。
3. 向量 Top-K 中与方向高度相关、且属于当前 NPC 图的节点。

语义锚点必须记录来源和置信度。是否加入搜索前沿由本地统一规则决定，不能由对话层预查或拼接关系上下文。

这意味着对外仍维持单一检索接口，同时把话题定向封装在 `RetrievalEngine` 内部。是否允许实体锚点直接成为额外前沿，会改变现有 Workstream 的“固定起点”口径；实施前必须明确选择：

1. 严格固定起点，只把锚点用于路径评分；或
2. 允许高置信实体锚点成为辅助前沿，并同步修订 Workstream / 必要 ADR。

第一版建议先采用方案 1，用真实失败样本证明两跳以上仍无法从固定起点抵达时，再评估方案 2。

### 6.2 搜索算法

建议使用受预算控制的 beam search，而不是继续增加逐跳 LLM 调用：

```text
frontier = fixed_starts
for depth in 1..max_depth:
    expand directional neighbors
    apply knowledge/access filters
    calculate path score
    keep top beam_width paths
    collect answer-bearing nodes
    stop if enough high-quality evidence or budget exhausted
```

第一版建议配置项：

1. `max_depth`：最大搜索深度，建议通过样本校准，不直接沿用固定 2 跳。
2. `beam_width`：每层保留路径数。
3. `max_expanded_edges`：单次检索最多访问边数。
4. `max_anchor_count`：语义锚点上限。
5. `final_memory_limit`：最终上下文条目上限。
6. `min_path_score`：继续扩张的最低路径质量。
7. `early_stop_margin`：高质量证据明显领先时提前停止。

深度、宽度和总访问量必须统一为搜索预算，不能只提高 `max_hops` 而不限制图爆炸。

### 6.3 路径评分

建议统一为路径级评分：

```text
path_score
= direction_relevance
+ edge_clarity
+ entity_alignment
+ relation_facet_alignment
+ time_alignment
+ source_reliability
+ target_context
+ node_importance
- depth_penalty
- repeated_topic_penalty
- uncertainty_penalty
```

要求：

1. 三种以上节点 / 边类型统一走评分策略表或 scorer interface，不继续增长大型 `switch / if`。
2. 明确实体命中是方向信号，不应无限覆盖来源可信度和知识权限。
3. 深路径不应天然优于浅路径；只有增加了与问题相关的新证据才值得继续扩张。
4. 同一事实的多个投影或相近节点应按来源 ID、语义和路径去重。

### 6.4 向量层职责

向量检索建议承担两种明确职责：

1. `anchor_discovery`：图邻接扩张无法覆盖语义方向时，提供少量候选锚点，再由本地图验证其归属、权限和连接关系。
2. `content_fallback`：图内证据不足时，补充当前 NPC 自己拥有的向量节点。

不得让向量结果绕过当前 NPC 的知识边界。向量命中的节点若不属于该 NPC、已归档且模式不允许、或知识权限不符，必须过滤。

## 7. 搜索终止与失败语义

应明确区分：

1. `sufficient_evidence`：已找到足够且一致的证据。
2. `budget_exhausted`：仍有候选，但达到边数 / 深度预算。
3. `no_reachable_path`：图中有相关锚点，但从当前口径无法抵达。
4. `knowledge_absent`：当前 NPC 图与向量层中没有相关事实。
5. `knowledge_forbidden`：存在候选，但观察者无权知道。
6. `direction_parse_failed`：LLM 与本地回退都无法形成有效方向。
7. `storage_unavailable`：图或向量存储不可用。

这些失败原因应该影响回答口径：不知道、想不起来、不方便说和系统失败不能混为一谈。

## 8. 与现有模式的关系

第一阶段只改 `player_dialogue`：

1. 玩家每轮仍使用当前发言、近期对白和会话摘要重新检索。
2. NPC-NPC 继续保持现有整段生成和轻量检索。
3. `nightly_impression` 继续保持现有较宽检索，待玩家模式验证后再决定是否复用方向 DTO。

若未来三种模式都采用统一搜索引擎，应通过 mode policy 配置预算、方向来源和终止条件，禁止复制三套检索器。

## 9. 诊断与控制要求

现有最终结果诊断不足以解释新流程。`aisc_debug.conversation_retrieval_snapshot` 至少应增加或关联：

1. LLM 原始方向输出的安全摘要。
2. 校验后的 `RetrievalDirection`。
3. mention 到稳定实体 ID 的解析结果。
4. 固定起点与语义锚点及其来源。
5. 实际搜索深度、展开边数、每层候选数和 beam 保留数。
6. 最终路径及主要分数组成。
7. 向量检索用途：`anchor_discovery` 或 `content_fallback`。
8. 被权限、归档、低分或预算淘汰的计数。
9. 明确的 `stop_reason` / `failure_reason`。

如测试需要稳定复现，应优先通过 `aisc_control` 提供编辑器专有的固定检索请求或重放入口，并同步文档；不能只依赖手工对话和 Console 文本。

## 10. 最小反馈环与验证场景

实施前应先建立 30 秒内可重复运行的检索评估 seam，输入固定图、当前发言和近期对白，断言方向、路径与最终节点。

至少覆盖：

1. “千早在哪”识别人物与定位意图，并沿人物相关路径寻找近期地点证据。
2. “那个面包店的女孩”通过描述解析到千早，而非只靠名字字符串。
3. “谁和樱关系最好”按关系维度搜索，不被玩家背景吸走。
4. “你为什么觉得龙之介有才能”沿人物 → 印象依据 → 事件路径回忆。
5. “上次你说有个人让你想起以前”结合近期对白和反思节点寻找来源。
6. 图中只有人物节点而无回答事实时返回 `knowledge_absent`，不由 LLM 补写。
7. 私密事实存在但观察者无权知道时返回 `knowledge_forbidden` 或不暴露候选内容。
8. LLM 超时、非法 JSON 和未知枚举时，本地回退仍能完成基础检索。
9. 深搜达到预算时返回 `budget_exhausted`，诊断能说明截断位置。
10. 与当前简单人名问题相比，延迟和 LLM 调用次数有明确上限。

## 11. 预计实现影响面

确认实施后，预计至少涉及：

1. `backend/src/memory/retrieval.py` 的路由编排与搜索职责。
2. 新的方向 DTO、解析 / 校验模块和本地搜索模块。
3. `memory_route` Prompt，或新增更准确命名的方向解析 task。
4. 模式配置、路径评分和向量锚点逻辑。
5. 玩家逐轮对话检索测试、真实竞争图 fixture 和性能评估脚本。
6. Unity 诊断 DTO、provider、`aisc_debug` / `aisc_control` action 与文档。
7. Memory / Dialogue Workstream 和代码目录 README。

当前 `RetrievalEngine` 已包含请求兼容、上下文构建、LLM 路由、本地评分、向量兜底、重排、clarity 恢复和日志等多项职责。若实施继续把方向解析与 beam search 塞入同一类，将触发类减重要求，必须先取得用户的“减重”指令。

该方向预计必然达到复杂实现阈值。确认实施时应创建唯一 plan，并在独立执行对话中实施。

## 12. 风险与待确认项

1. LLM 浅层方向可能过度概括或误解代词；必须保留原文 mention、本地校验和确定性回退。
2. 深搜可能增加 SQLite / LanceDB 查询次数；需要批量邻接读取、缓存和总边预算。
3. 高置信实体锚点是否允许成为辅助前沿涉及既有固定起点口径，必须在实施前明确。
4. 新评分如果同时引入过多因素，可能难以校准；第一版应先用真实问题集评估，再确定权重。
5. `knowledge_forbidden` 的判定依赖节点具有来源 / 权限元数据；初始投影未实施前只能对已有元数据做有限过滤。
6. LLM 一次调用虽然比逐跳稳定，但简单问题可能不值得调用；是否保留确定性快速路径需要用延迟与准确率样本决定。

## 13. 验收标准

1. 玩家对话每轮最多进行一次方向 LLM 调用，不再逐跳调用 LLM 选边。
2. 本地算法能在受控预算内搜索超过两跳，并提供完整路径证据。
3. 描述性称呼、关系追问、因果追问和近期指代的命中率明显优于当前方案。
4. 图内无事实时不产生虚构答案，能明确区分无知识、不可达、无权限和预算截断。
5. 检索延迟、访问边数、向量调用和最终上下文长度均有上限。
6. `aisc_debug` 能解释方向、锚点、搜索过程、最终路径和停止原因。
