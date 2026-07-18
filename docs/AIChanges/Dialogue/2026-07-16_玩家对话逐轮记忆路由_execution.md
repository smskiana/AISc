# 玩家对话逐轮记忆路由执行记录

> 设计方案: [ConversationMemoryRoutingExecutionPlan.md](../../Workstreams/Dialogue/ConversationMemoryRoutingExecutionPlan.md)

> 状态说明：本记录保留首次实现的实际证据，但其中“话题实体加入检索起点、预查话题人物关系”的实现已被判定为偏离需求，不代表当前正确工程口径。后续必须按修订后的原执行案纠正；当前口径以 Workstream 和修订执行案为准。

## 范围

本轮以现有执行案为唯一方案来源。执行中用户明确取消 NPC-NPC 逐轮检测，因此实际范围收敛为玩家-NPC逐轮会话工作记忆、实体识别、结构化图检索和诊断同步；NPC-NPC 保持原有整段生成与 Unity `COMPLETE` 后提交语义。

## 实际改动

1. 新增对话 DTO、稳定实体解析器和 `ConversationMemoryCoordinator`，保存最近八轮原文、滚动摘要、已识别实体和逐轮诊断。
2. `RetrievalEngine` 新增 `RetrievalRequest / RetrievalResult`，同时保留旧位置参数兼容入口。
3. 图检索起点支持说话者 self、玩家参与者和当前话题人物；路由 Prompt 与向量 query 包含当前发言、话题实体、会话摘要和近期对白。
4. 玩家每次发言都会刷新动态 system context；参与者关系只负责语气，话题人物关系只负责回答内容。
5. 取消、LLM 失败和非正常结束会释放工作记忆且不提交持久化短期记忆；正常结束仍沿用现有整段摘要提交。
6. Unity 诊断缓存新增逐轮对话检索 DTO，`aisc_debug` 新增 `conversation_retrieval_snapshot`，并修复自定义工具缺少 MCP 参数 schema 的问题。

## 问题与修正

1. 首次 Play 验证发现把 `bond` 错查到 `npc_impressions`，实际字段位于 `npc_bonds`；已改为分别读取两张表并补回归测试。
2. 近期历史中的玩家参与者一度重复进入话题实体；已收紧为参与者只有在当前发言明确提及时才兼任话题实体。
3. NPC-NPC 逐轮实现已按用户最新指示完整撤销，现有社交生成和提交测试保持通过。

## 验证

1. 后端全量单元测试：43 项通过。
2. 范围调整后相关测试：19 项通过。
3. `dotnet build AISc.sln --no-restore`：0 错误；保留项目既有程序集版本冲突警告。
4. Unity EditMode `AiscDiagnosticsTests`：5/5 通过。
5. Unity Play Mode：`aisc_debug.health_report=ready`，后端连接和协议握手正常，Console 无错误。
6. 真实九条对话中询问“千早是谁？”后，诊断确认：
   - `topic_entities` 包含 `chihaya`；
   - `start_node_ids` 同时包含 self、player 和 chihaya 人物节点；
   - 参与者使用 `kujo -> player` bond/impression；
   - 话题人物使用 `kujo -> chihaya` bond/impression；
   - `vector_query_preview` 包含“千早是谁？”和“千早”；
   - `persistence_status=working_memory_only`，逐轮过程未写持久化短期记忆。

## 未实施

1. NPC-NPC 逐轮实体识别和逐轮图检索：按用户明确指示不实施。
2. NPC-NPC逐轮相关完成标准与测试不属于本轮验收范围。
