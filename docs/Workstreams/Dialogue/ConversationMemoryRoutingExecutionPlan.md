# 玩家对话逐轮文本刷新与图检索执行案

## 文档状态

- Status：Implemented（真实对话场景验收待补）
- 主要功能域：Dialogue
- 关联功能域：Memory、TestingAndDiagnostics
- 既有执行记录：[2026-07-16_玩家对话逐轮记忆路由_execution.md](../../AIChanges/Dialogue/2026-07-16_玩家对话逐轮记忆路由_execution.md)
- 纠正执行记录：[2026-07-16_玩家对话逐轮记忆路由纠正_execution.md](../../AIChanges/Dialogue/2026-07-16_玩家对话逐轮记忆路由纠正_execution.md)
- 执行补充：为完成真实对话验收，允许新增 `UNITY_EDITOR` 条件编译保护的白名单 `aisc_control.start_new_game`；该工具及对应业务入口不得进入 Player 构建。
- 2026-07-16 口径修订：不做 NPC-NPC 逐轮检测；不识别话题实体作为检索起点；不预查话题人物 impression / bond。唯一目标是玩家每次发言后，用最新对话文本重新执行现有图检索。
- 正式纠正实现必须在新的执行对话中开始，并以本文件为唯一方案来源。

## 一、问题定义

当前玩家与 NPC 的正式对话只在会话开始时执行一次记忆检索。后续玩家发言虽然会追加到回答模型的 messages，但不会重新进入图路由 Prompt，也不会刷新向量兜底 query。

例如玩家向九条莲询问“千早是谁？”时：

1. 回答模型能看到“千早是谁？”。
2. 图检索仍然复用开场时的旧结果。
3. 图路由没有机会根据“千早是谁？”重新选择边。
4. 向量兜底也没有使用这句最新问题。

缺陷是“检索没有刷新当前对话文本”，不是“系统缺少话题实体起点”。

## 二、目标行为

玩家每次发言后执行以下流程：

```text
收到当前玩家发言
→ 将当前发言追加到现有对话历史
→ 取当前发言和最近若干轮对白
→ 使用现有图检索起点规则重新执行图路由
→ 每一跳路由参考最新对话文本
→ 图结果不足时，用最新对话文本构建向量 query
→ 用本轮新检索结果刷新动态 Prompt
→ 生成 NPC 回复
→ 将有效回复追加到对话历史
```

本轮不新增实体识别、实体消歧或定向人物检索流程。

## 三、核心边界

### 3.1 图检索起点保持原有规则

不得因为当前发言提到千早、和叶、地点或物品，就把对应节点直接加入 `start_node_ids`。

```text
禁止：self + player + chihaya
禁止：先识别 chihaya，再从 chihaya 人物节点开始检索
禁止：先读取 kujo -> chihaya impression / bond，再注入回答上下文
```

图检索继续使用修改前已经存在的起点策略。若当前策略是 `self + 当前对话对象`，本轮保持该策略；不得借本任务重新设计起点。

“千早是谁？”只能作为图路由的语义上下文。图路由必须根据候选边和当前问题自行决定是否走向千早相关节点。

### 3.2 当前对话文本只是路由依据

每轮传给检索器的对话文本至少包含：

1. 当前玩家发言完整文本。
2. 最近 4-8 轮有效对白。
3. 当前 NPC 和玩家的既有参与者关系语境。
4. 当前地点和游戏时间。

更早对白是否做摘要由 Prompt 体积决定，不是首期必需能力。不得为了本任务引入复杂实体状态。

### 3.3 图路由负责发现关联

系统不能先替图路由决定“应该查询千早”。正确行为是：

```text
固定起点
→ 候选边
→ 路由 Prompt 看到“千早是谁？”
→ 图路由选择与千早相关的边
→ 命中相关人物、关系、事件或反思节点
→ 重建回答所需记忆上下文
```

只有图实际命中相关节点后，节点内容和沿途关系语义才可以进入检索结果。

## 四、检索接口调整

保持 `RetrievalEngine` 的图结构和起点选择职责不变，只增加本轮对话文本输入。

建议请求结构：

```python
@dataclass
class RetrievalRequest:
    npc_id: str
    target_id: str
    query_text: str
    recent_dialogue: list[ConversationTurn]
    location_id: str
    game_time: str
    mode: Literal["player_dialogue"]
```

不包含：

```text
topic_entity_ids
topic_start_node_ids
topic_impressions
topic_bonds
```

返回结果继续包含：

```python
@dataclass
class RetrievalResult:
    rebuilt_context: str
    start_node_ids: list[str]
    selected_edge_ids: list[str]
    retrieved_node_ids: list[str]
    vector_query_preview: str
    fallback_used: bool
    diagnostics: dict
```

旧调用入口可以短期兼容，但玩家后续发言必须使用包含 `query_text` 和 `recent_dialogue` 的新入口。

## 五、路由 Prompt 调整

每一跳路由 Prompt 在原有状态、地点、近期记忆、前沿节点和候选边基础上增加：

```text
当前玩家发言完整文本
最近若干轮对白
```

路由规则：

1. 当前玩家发言是本轮相关性判断的主要依据。
2. 不得把从文本中提取出的名字直接转换成检索起点。
3. 不得因为当前对话对象是玩家，就始终偏向固定玩家背景关键词。
4. relationship 边是否被选择应由当前发言、边语义、方向、clarity 和终点内容共同决定。
5. 图路由无法找到相关内容时，允许自然返回弱结果或进入向量兜底，不得通过硬编码人物关系补答案。

## 六、向量兜底调整

图路由结果不足时，向量 query 由以下内容组成：

```text
当前玩家发言
+ 最近若干轮对白
+ 当前地点
+ 最多 2-3 条持久化近期记忆摘要
```

不得加入预解析的话题实体名称列表，也不得继续只使用“目标人物 + 地点 + 固定玩家背景关键词”。

## 七、玩家对话接入

### 7.1 开场

开场继续按现有流程执行一次检索，不改变起点规则：

```text
Unity DIALOGUE_READY
→ 构建稳定角色和现场上下文
→ 以开场事件文本执行现有图检索
→ 生成 NPC 开场白
```

### 7.2 后续玩家发言

```text
收到 choice_text
→ 追加玩家发言
→ 使用 choice_text + 最近对白重新调用 RetrievalEngine
→ 用新 RetrievalResult 替换上一轮动态记忆上下文
→ 生成 NPC 回复
→ 追加 NPC 回复
```

每轮刷新：

1. 当前发言。
2. 最近对白。
3. NPC 当前状态、地点和时间。
4. 图路由结果。
5. 向量兜底结果。

保持稳定：

1. NPC profile。
2. 当前对话参与者。
3. 图检索起点策略。
4. 参与者 impression / bond 的既有用途。

## 八、职责边界

### DialogueService

只负责：

```text
接收玩家发言
→ 整理本轮检索文本
→ 调用 RetrievalEngine
→ 调用 PromptBuilder 和 LLM
→ 维护完成、取消和失败生命周期
```

不得加入实体识别、实体缓存、话题人物关系查询或定向节点选择。

### PromptBuilder

只负责格式化稳定角色信息、现场感知、参与者关系和本轮检索结果。不得决定图检索对象或起点。

### RetrievalEngine

继续负责图起点、候选边、路由、节点重建和向量兜底。本轮只让它看到最新对话文本，不替它预选答案方向。

## 九、持久化规则

本轮不改变现有整段对话结束后提交摘要的语义：

1. 每轮原始对白只存在于活跃会话历史中。
2. 不得在每次检索前写入 `short_term_memories`。
3. 正常结束后按现有口径提交整段摘要。
4. 取消、失败和生成错误不得提交未完成内容。

## 十、诊断同步

`aisc_debug` 的玩家对话检索快照应包含：

```text
conversation_id
speaker_id
participant_ids
current_utterance
recent_dialogue_preview
start_node_ids
selected_edge_ids
retrieved_node_ids
vector_query_preview
vector_fallback_used
failure_reason
```

不得把以下字段作为新检索设计的完成证据：

```text
topic_entities
topic_impressions
topic_start_node_ids
```

关键诊断断言：提问“千早是谁？”后，`start_node_ids` 与原有起点策略一致；当前问题出现在路由输入和向量 query 中；最终是否命中千早由图路径结果证明。

## 十一、测试计划

### 11.1 玩家逐轮刷新

1. 开场检索后，玩家第二轮发言必须触发新的 `retrieve` 调用。
2. 第二轮 `query_text` 必须等于当前玩家完整发言。
3. 最近对白必须包含上一轮 NPC 回复和当前玩家发言。
4. 第二轮动态记忆上下文必须替换开场检索结果，不能继续复用旧结果。

### 11.2 图能力边界

1. 玩家问“千早是谁？”时，`chihaya` 不得被直接加入 `start_node_ids`。
2. 不得在路由前直接查询或注入 `kujo -> chihaya` impression / bond。
3. 路由 Prompt 必须包含“千早是谁？”。
4. 固定真实图数据下，图路由应能通过候选边命中千早相关节点；测试应断言实际 `selected_edge_ids` 和 `retrieved_node_ids`。
5. 如果图中不存在可达路径，测试应允许无命中或向量兜底，不得硬编码返回千早关系。
6. 第二轮改问和叶时，起点保持不变，但路由选择和检索结果应随文本变化。

### 11.3 向量兜底

1. 当前发言必须出现在 `vector_query_preview`。
2. 最近对白应进入 query。
3. query 不得包含单独构造的话题实体名称列表。

### 11.4 生命周期

1. 取消和 LLM 异常释放活跃会话历史。
2. 异常轮次不得提交短期记忆。
3. 正常结束仍只提交一次整段摘要。
4. NPC-NPC 现有整段生成和 `COMPLETE` 提交测试保持不变。

## 十二、实施步骤

### 阶段 A：撤销错误定向设计

1. 删除或停用玩家对话链中的 `DialogueEntityResolver`。
2. 从 `RetrievalRequest` 删除 `topic_entity_ids` 和参与者节点集合扩张语义。
3. 恢复修改前的图起点选择规则。
4. 删除路由前的 `topic_impressions / topic_bonds` 查询与 Prompt 注入。

验收：询问千早时 `start_node_ids` 不包含因本轮文本额外加入的千早节点。

### 阶段 B：保留逐轮文本刷新

1. 每次玩家发言重新调用检索器。
2. 传入当前发言和最近对白。
3. 路由 Prompt 与向量 query 使用这些文本。
4. 用本轮检索结果替换上一轮动态上下文。

验收：相同起点下，不同玩家问题产生不同路由选择或兜底 query。

### 阶段 C：诊断与验证

1. 收敛诊断 DTO，移除 topic entity 作为成功证据的口径。
2. 补固定图回归测试，断言千早不是起点但可以成为实际命中节点。
3. 运行后端全量测试和 Unity EditMode 测试。
4. 使用 Unity Play Mode 实际询问“千早是谁？”，通过 `aisc_debug` 检查起点、选边、命中节点和向量 query。

## 十三、预计涉及文件

现有文件：

```text
backend/src/application/dialogue_service.py
backend/src/dialogue/prompt_builder.py
backend/src/dialogue/conversation_context.py
backend/src/dialogue/conversation_memory.py
backend/src/dialogue/entity_resolver.py
backend/src/memory/retrieval.py
backend/tests/test_conversation_memory_routing.py
Assets/Scripts/Diagnostics/DiagnosticModels.cs
Assets/Scripts/Diagnostics/AiscDiagnostics.cs
Assets/Scripts/Core/WebSocketClient.cs
Assets/Scripts/Editor/Diagnostics/AiscDebugMcpTool.cs
Assets/Tests/Editor/AiscDiagnosticsTests.cs
docs/Workstreams/Dialogue/README.md
docs/Workstreams/Memory/README.md
```

不修改：

```text
backend/src/npc/npc_dialogue.py
backend/src/npc/social_session.py
NPC-NPC Unity 播放协议和资产
```

## 十四、风险与控制

### 图路由无法找到话题

这是需要真实暴露和测试的图能力，不得用话题人物起点或预查 impression 掩盖。若真实图不可达，应单独诊断建图、边方向、候选裁剪或路由 Prompt，而不是在对话层走后门。

### Prompt 体积增加

当前发言完整保留，近期对白限制为 4-8 轮；首期不强制新增滚动摘要系统。

### 旧动态上下文残留

每轮必须替换上一轮检索结果，测试需确认不会同时保留开场和当前轮的两份动态记忆块。

## 十五、完成标准

只有同时满足以下条件才可宣称完成：

1. 玩家每次发言都会用当前完整文本重新执行图检索。
2. 最近对白进入每一跳路由 Prompt。
3. 当前发言进入向量兜底 query。
4. 图检索起点保持修改前的既有策略，不随当前文本提到的人物变化。
5. 不做话题实体识别后定向起点。
6. 不在图路由前预查或注入话题人物 impression / bond。
7. “千早是谁？”测试中千早不是起点；若图可达，千早相关节点通过实际选边和路径被命中。
8. 不可达时允许图无结果或向量兜底，不得硬编码人物答案。
9. 每轮原始对白不写入持久化短期记忆，正常结束仍只提交一次摘要。
10. NPC-NPC 保持现有整段生成与 `COMPLETE` 提交语义。
11. `aisc_debug` 能展示当前发言、固定起点、选边、命中节点和向量 query。
12. 后端测试、真实图验证、Unity EditMode 和 Play Mode 验证全部通过。
