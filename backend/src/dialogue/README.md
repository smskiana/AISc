# Dialogue 模块

## 文件夹功能

负责后端对话生成、prompt 上下文和回复处理。

## 文件夹内容

包含玩家对话、NPC 闲聊、快捷回复、现场感知和角色语义。当前产品口径见 Dialogue Workstream。

玩家正式对话的逐轮动态上下文由 `conversation_memory.py` 编排，`conversation_context.py` 定义 DTO；每轮以最新发言重新检索，检索层才可按确定性规则选择至多一条相关近期对白，不在对话层解析话题实体或扩张图起点。`entity_resolver.py` 当前不接入玩家正式对话链。NPC-NPC 对话仍保留整段生成方式。

后端 LLM 调用不设置 `max_tokens` 硬上限；对白长度、建议数量和摘要格式由 Prompt 软约束，输出继续经过既有解析、截断与兜底处理。

对话的三类 Prompt 由 `src/prompting.PromptAssembler` 按 `player_dialogue`、`npc_dialogue` 和 `player_reply_suggestions` task 组装。

LongCat 的思考模式由 `llm_client.py` 统一通过官方请求体 `thinking.type` 控制，不向业务 messages 注入 `/no_think`。`settings.yaml` 的 `llm.thinking_mode` 可设为 `enabled`、`disabled` 或空字符串；空值表示使用供应商默认行为。后端 `/api/health` 暴露当前模式。
对话的三类 Prompt 由 `src/prompting.PromptAssembler` 按 `player_dialogue`、`npc_dialogue` 和 `player_reply_suggestions` task 组装；本模块只收集动态上下文。

快捷回复通过 `player_reply_suggestions` 传入明确的 `player_name`、`npc_name`、NPC 关系/语气背景和玩家记忆。解析收口只拒绝确定性的 NPC 名称前缀与开头括号舞台动作，再用既有 fallback 补足三条；不在业务层做中文语义主体猜测。`reply_suggestion_diagnostics.py` 保存不含完整 Prompt 或原始输出的有界 trace，供只读诊断入口使用。
