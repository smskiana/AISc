# LongCat 官方 Thinking 参数纠正执行案

> 执行记录: [2026-07-17_LongCat官方Thinking参数纠正_execution.md](2026-07-17_LongCat官方Thinking参数纠正_execution.md)

## 需求理解

撤销错误的 `/no_think` system Prompt 注入，按照 LongCat 官方聊天补全文档，通过请求体 `thinking: {"type":"disabled"}` 关闭思考。

## 方案

1. 配置从 `llm.thinking_instruction` 改为 `llm.thinking_mode`，允许 `enabled`、`disabled` 或空字符串。
2. 默认配置为空，避免非 LongCat 供应商收到不支持的扩展字段；当前 LongCat 本地配置显式设为 `disabled`。
3. `LLMClient` 不再修改 messages，统一把思考模式合并到 OpenAI SDK 的 `extra_body.thinking.type`。
4. 调用方已有 `extra_body` 时保留其他字段，只覆盖集中管理的 `thinking` 字段。
5. 更新健康诊断、测试和 Dialogue 入口文档；原错误 plan / execution 标记为已被纠正。

## 风险与验收

1. 非 LongCat 模型可能不支持 `thinking`；空配置时完全不发送扩展字段。
2. 验收同步与流式请求参数准备逻辑，确认 messages 不变、`extra_body` 正确合并、空配置不发送 thinking。
3. Python 编译和后端全量测试必须通过。
