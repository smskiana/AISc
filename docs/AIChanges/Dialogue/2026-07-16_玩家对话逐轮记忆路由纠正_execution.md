# 玩家对话逐轮记忆路由纠正执行记录

> 设计方案: [ConversationMemoryRoutingExecutionPlan.md](../../Workstreams/Dialogue/ConversationMemoryRoutingExecutionPlan.md)

## 范围

本轮以修订后的原执行案为唯一方案来源，纠正首次实现中的话题实体定向起点和话题人物关系预查；保留玩家每轮最新文本刷新、近期对白窗口、滚动摘要、结构化检索结果和整段会话提交语义。NPC-NPC 链路不修改。

## 实际改动

1. `ConversationMemoryCoordinator` 移除 `DialogueEntityResolver` 依赖、已识别实体状态和话题人物 impression / bond 查询，只读取当前对话参与者关系。
2. `RetrievalRequest` 移除 `topic_entity_ids`；`RetrievalEngine` 的图起点恢复为 self 与当前对话对象，当前发言和近期对白只进入路由语义与向量 query。
3. 路由 Prompt 移除话题实体字段；本地候选排序改为通用文本字符相关性，不预解析人物名称或硬编码人物关系。
4. `PromptBuilder` 移除话题实体和话题人物关系注入，每轮仍以新检索结果替换旧动态 system context。
5. `aisc_debug` 会话检索 DTO 移除 `topic_entities / topic_impressions`，新增 `recent_dialogue_preview`，继续保留固定起点、选边、命中节点、向量 query、失败原因和持久化状态。
6. 同步 Dialogue、Memory Workstream 和代码目录 README。
7. 新增 `UNITY_EDITOR` 条件编译保护的 `aisc_control.start_new_game`，并在 `StartMenuController` 提供同样仅编辑器存在的白名单入口；不改变 `aisc_debug` 的只读契约，Player 构建不包含控制工具和业务入口。

## 验证

1. Python 编译检查通过。
2. 后端全量 `unittest`：43 项通过。
3. 固定图回归证明询问“千早是谁？”时起点只有 `self + player`，随后沿 `edge_kujo_chihaya` 命中 `chihaya` 节点；当前发言和近期对白均进入 `vector_query_preview`。
4. Unity 脚本刷新完成，Console 0 error。
5. Unity EditMode `AiscDiagnosticsTests`：6/6 通过，包含 `recent_dialogue_preview` DTO 解析断言。
6. `dotnet build AISc.sln --no-restore`：0 错误；保留项目既有程序集版本冲突与未赋值字段警告。
7. Unity MCP 导入并发现 `aisc_control`；`start_new_game` 成功发送 `GAME_START/NEW_GAME`，随后 `aisc_debug.health_report.status=ready`，5 个 NPC 状态和实体均已生成。
8. Play Mode 真实启动九条对话并发送“千早是谁？”：诊断确认 `start_node_ids` 始终只有 self 与 player；当前发言进入 `recent_dialogue_preview` 和 `vector_query_preview`；最终检索到的 `node_kujo_81bb0c43` 是人物“千早”，但本轮图选边仍走玩家背景边，千早节点由向量兜底命中。
9. Unity Console 无 Error/Warning；但当前 `openai/LongCat-2.0` 的三轮九条回复均为空，后端记录 `chars=0`。最小 API 请求证明供应商会同时返回 `reasoning_content` 和 `content`，因此高概率是复杂 Prompt 下 `max_tokens=120` 被推理内容耗尽，而不是 Unity 丢包或本轮检索失败。

## 问题与处理

1. 初次调用静态 `aisc_debug` 包装器时参数 schema 未暴露，改用 Unity MCP 的 `execute_custom_tool` 调用项目自定义工具；项目工具本体可正常返回结构化诊断。
2. 尝试通过编辑器游戏窗口进入真实场景时检测到用户输入，立即停止界面自动化；随后改用用户要求的 `UNITY_EDITOR` 白名单控制钩子完成开局。
3. 验证过程中曾误把 `compileall` 与测试并行启动；两者均成功且未发生 pycache 冲突，但该方式不符合既有错误预防规则，后续验证按串行执行。
4. 新增 C# 测试初次缺少 `using UnityEngine;` 导致 `JsonUtility` 编译失败；补齐引用后 Unity Console 恢复为 0 error。
5. 外部新增 `AiscControlMcpTool.cs` 后普通刷新未注册工具；按既有错误预防规则使用 Unity MCP `manage_asset import` 显式导入后，`aisc_control` 正常出现在 custom tools 列表。
6. `aisc_control.start_new_game` 在 Play Mode 初期可能早于 WebSocket ready，当前需要读取 `health_report` 后重试；返回错误清楚，但自动化易用性一般。
7. 当前控制钩子没有 `start_dialogue / send_player_choice / end_dialogue`，真实对话测试仍需 Unity MCP `execute_code` 调用现有公开 API；若后续经常做对话验收，应再按白名单 action 扩充。
8. `conversation_retrieval_snapshot` 会返回 Unity 缓存的同一会话多轮历史，不是默认只返回最新一轮；对比轮次有用，但自动断言前需要自行选取最后一项。

## 未完成项

1. LongCat 当前会生成空正文，需单独决定是提高对话输出预算、禁用推理或增加空正文失败保护；该问题不属于本轮记忆路由纠正。
2. 图路由没有沿图边命中千早，只由向量兜底命中；若产品要求必须通过图路径发现千早，应单独检查建图可达性、边方向、候选裁剪和路由 Prompt。
3. `aisc_control` 的连接等待和对话白名单 action 属于后续易用性增强，不影响本轮只读诊断证据。
