# LongCat 官方 Thinking 参数纠正执行记录

> 设计方案: [2026-07-17_LongCat官方Thinking参数纠正_plan.md](2026-07-17_LongCat官方Thinking参数纠正_plan.md)

## 实际改动

1. 移除把 `/no_think` 作为首条 system message 注入所有业务 Prompt 的错误实现。
2. 配置改为 `llm.thinking_mode`，支持 `enabled`、`disabled` 或空字符串；当前 LongCat 配置为 `disabled`。
3. `LLMClient` 按官方 OpenAI 兼容接口格式，通过 `extra_body={"thinking":{"type":"disabled"}}` 发送思考模式。
4. 流式与非流式调用统一使用请求参数准备入口；已有 `extra_body` 的其他字段会被保留，调用方字典不会被原地修改。
5. 空模式不发送 `thinking` 字段，以兼容不支持该扩展的其他供应商。
6. `/api/health` 改为返回 `llm_thinking_mode`，值为空时显示 `provider_default`。
7. 同步 Dialogue Workstream、代码 README，并把旧 `/no_think` plan / execution 标记为错误且已被本记录取代。

## 测试

1. 覆盖 `disabled` 模式的官方请求体结构。
2. 覆盖已有 `extra_body` 字段的无损合并。
3. 覆盖空模式不发送 thinking。
4. 覆盖 YAML 在 `disabled` 与空值之间切换。

## 验证

1. `python -m compileall -q backend/src backend/tests` 通过。
2. 后端全量 `unittest`：47 项通过。
3. 正式代码、配置和测试中无 `thinking_instruction`；`/no_think` 仅在当前口径文档中作为禁止方式说明，并在旧审计记录中标明错误。
4. 使用当前 LongCat 配置发送最小真实请求：约 1.98 秒返回“测试成功”，`reasoning_content` 不存在，`finish_reason=stop`。

## 诊断钩子检查

本次修正后端供应商请求语义。Unity `aisc_debug` 不承载后端供应商参数；后端 `/api/health` 已同步为 `llm_thinking_mode`，足以确认当前模式。`aisc_control` 不适用。

## 未完成项

无。
