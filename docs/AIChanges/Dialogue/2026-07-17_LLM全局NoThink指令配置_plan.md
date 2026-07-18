# LLM 全局 No Think 指令配置执行案

> 执行记录: [2026-07-17_LLM全局NoThink指令配置_execution.md](2026-07-17_LLM全局NoThink指令配置_execution.md)
>
> 本方案采用 `/no_think` system Prompt，后经 LongCat 官方文档确认方式错误。纠正方案见 [2026-07-17_LongCat官方Thinking参数纠正_plan.md](2026-07-17_LongCat官方Thinking参数纠正_plan.md)，不得再按本方案实现。

## 需求理解

为后端所有 LLM 请求增加一个集中、方便替换或关闭的思考控制指令。默认使用 `/no_think`，避免模型长时间输出推理内容；不得把该指令散落到各业务 Prompt。

## 方案

1. 在全局配置增加 `llm_thinking_instruction`，YAML 键为 `llm.thinking_instruction`，默认值为 `/no_think`。
2. `LLMClient` 在实际请求前复制消息并把非空指令作为第一条 system message 注入，不修改调用方原始列表。
3. 流式与非流式请求统一走同一消息准备入口。
4. 配置为空字符串时不注入，便于切换到不支持该指令的模型。
5. 增加配置解析和消息注入测试，更新 Dialogue 入口文档。

## 涉及文件

- `backend/src/config.py`
- `backend/src/application/runtime.py`
- `backend/src/dialogue/llm_client.py`
- `backend/config/settings.yaml`
- `backend/tests/test_protocol_execution_loop.py`
- Dialogue Workstream、代码 README 与 execution

## 风险与验收

1. 风险：不同模型识别的指令不同；通过配置项替换或置空解决。
2. 风险：原消息被原地修改导致重复注入；客户端必须构造新列表。
3. 验收：同步与流式底层请求均收到首条 `/no_think` system message，调用方消息保持不变，配置为空时不注入，全量测试通过。
