# 工作流：对话系统

## 当前目标

让玩家对话、NPC 闲聊和快捷回复能够稳定使用现场感知、角色视觉标签和记忆检索，同时避免虚构不存在的物品或亲历未发生事件。

## 当前工程口径

1. 玩家正式对话、NPC-NPC 闲聊、快捷回复都会注入现场感知。
2. 地点、物品、NPC profile 提供视觉、五感、话题钩子和称呼建议。
3. 玩家默认昵称通过 `player_name.py` 渲染，不在 prompt 中硬编码“小李”为固定本名。
4. 首遇 prompt 不诱导“好久不见 / 你一点都没变”这类亲眼确认式寒暄。
5. 事实守门只拦未发生玩家行动的亲历式断言，传闻式表达交给时间语义和记忆系统。
6. 玩家正式对话采用 `DIALOGUE_START / DIALOGUE_PREPARED / DIALOGUE_READY` 握手，后端只在前端现场就绪后生成内容。
7. 同步 LLM 流已桥接到工作线程，对话生成期间后端 WebSocket 继续监听结果和取消消息。
8. NPC 移动中时 Prompt 显示“从出发地到目标地的途中”，并禁止加载任一地区的固定现场感知。
9. NPC-NPC 对话采用 `NPC_SOCIAL_PREPARE / READY / FAILED / COMPLETE` 闭环；后端只在 Unity 会合 READY 后生成，并只在完整播放 COMPLETE 后写记忆。
10. 玩家正式对话的目标口径是每次玩家发言都用最新发言和近期对白重新执行现有图检索；图起点保持既有策略，不做话题实体定向起点或话题人物关系预查。
11. NPC-NPC 继续使用现有整段生成方式，不做逐轮实体识别和逐轮图检索。
12. 后端 LLM 调用不设置 `max_tokens` 硬上限；对白长度、结构化字段和候选数量由 Prompt 软约束，解析与业务校验继续负责收口。
13. LongCat 思考模式通过官方请求体 `thinking.type` 控制；当前 `llm.thinking_mode=disabled`，不得使用 `/no_think` system Prompt 代替。空配置表示使用供应商默认行为。
14. 后端对话、行为和记忆 Prompt 由 `backend/src/prompting/` 统一按 task 组装，角色与地点风格优先来自 profile 标签。
15. 记忆路由策略由后端 `memory_retrieval.yaml` 按业务 mode 选择；对话调用层只提交 `RetrievalRequest`，不携带 strategy、实体或 beam 覆盖。
16. 玩家快捷回复固定表达“玩家下一句对当前 NPC 说的话”：Prompt 使用独立 `player_name` / `npc_name`，NPC 关系与语气只作背景；确定性收口拒绝 NPC 名称前缀和开头括号动作，并由 `aisc_debug.player_reply_suggestion_snapshot` 提供有界安全 trace。

## 已完成阶段

1. 快捷回复角色标签注入。
2. 对话感知标签接入。
3. 快捷回复称呼硬规则收敛。
4. 玩家昵称语义收敛。
5. 对话加载态、移动锁定、对话时停等前端体验补齐。
6. 玩家对话准备与现场就绪握手。
7. 同步 LLM 流已移入工作线程，生成期间 WebSocket 可继续处理取消和行为结果。
8. NPC 移动中的 transit 位置会渲染为途中语义，不加载出发地或目标地现场感知。
9. NPC-NPC 社交会合握手、120 秒监督超时和播放完成提交已接入。
10. 玩家-NPC 逐轮文本刷新、结构化图检索和诊断快照已纠正：每轮使用最新发言和近期对白，图起点保持既有策略，不预查话题人物关系。
11. 玩家、NPC-NPC 和夜间记忆检索共用后端 trace；Unity `aisc_debug.memory_retrieval_snapshot` 可按 mode / strategy 读取原问题、检索想法、单次向量、图候选和最终原子条目安全诊断。
12. 玩家快捷回复主体契约与安全诊断已接入：真实 LLM 首轮/续轮已覆盖鹿岛樱、千早、和叶、龙之介、九条。

## 下一阶段建议

1. 用真实 LLM 长测观察现场物件引用是否自然。
2. 检查和叶、龙之介、九条等称呼是否只依赖角色视觉和关系语境。
3. 如果 prompt 变慢，优先压缩 `PerceptionContextBuilder` 的物品和 spot 输出。
4. 在旧书店、派出所、面包店、河边各做对白样本。

## 暂缓事项

1. 不新增大段硬性称呼禁令。
2. 不把不存在的地点 / 行为自由交给 LLM 生成。
3. 不用 prompt 白名单长期替代记忆系统事实。

## 相关设计与决策

1. `docs/DesignDocs/CharacterPresets.md`
2. `docs/DesignDocs/MemoryArchitecture.md`
3. `docs/Workstreams/Memory/README.md`
4. `docs/Workstreams/Dialogue/ConversationMemoryRoutingExecutionPlan.md`：玩家每轮用最新对话文本重新执行现有图检索的纠正执行案；不含 NPC-NPC 逐轮检测。

## 相关执行证据

详见 `docs/AIChanges/Dialogue/README.md`。
后端对话、行为和记忆 Prompt 由 `backend/src/prompting/` 统一按 task 组装，角色与地点风格优先来自 profile 标签。
