# LLM 全局 No Think 指令配置执行记录

> 设计方案: [2026-07-17_LLM全局NoThink指令配置_plan.md](2026-07-17_LLM全局NoThink指令配置_plan.md)
>
> 本记录中的 `/no_think` system Prompt 方式已确认错误并被移除。最终口径见 [2026-07-17_LongCat官方Thinking参数纠正_execution.md](2026-07-17_LongCat官方Thinking参数纠正_execution.md)。

## 实际改动

1. `Config` 新增 `llm_thinking_instruction`，对应 YAML 键 `llm.thinking_instruction`，默认值为 `/no_think`。
2. `runtime` 初始化 LLM 时传入该配置。
3. `LLMClient` 新增统一消息准备入口；流式与非流式请求都会复制原消息，并在配置非空时把指令作为第一条 system message 注入。
4. `backend/config/settings.yaml` 当前显式配置 `/no_think`；置空即可关闭，也可以替换为其他模型支持的指令。
5. `/api/health` 新增 `llm_thinking_instruction_enabled`，只暴露是否启用，不回显具体指令。
6. 同步 Dialogue Workstream 与代码目录 README。

## 测试

1. 新增指令注入测试：确认 `/no_think` 位于首条消息，原消息列表不被修改。
2. 新增空配置测试：确认不注入额外 system message。
3. 新增 YAML 配置测试：确认指令可替换为 `No_think`，也可通过空字符串关闭。

## 验证

1. `python -m compileall -q backend/src backend/tests` 通过。
2. 后端全量 `unittest`：46 项通过。
3. 静态检查确认同步 `chat` 与流式 `chat_stream` 均调用统一 `_prepare_messages`。

## 诊断钩子检查

本次改变所有后端 LLM 请求的模型控制指令。Unity `aisc_debug.health_report` 不承载后端供应商配置，因此在后端既有 `/api/health` 增加启用状态字段；未修改 `aisc_control`，因为该配置不属于运行时控制动作。

## 未完成项

未发送真实 LongCat 请求验证供应商对 `/no_think` 的实际响应时间变化，避免在自动测试中产生外部 API 调用和费用；调用链与配置注入已由自动测试覆盖。
