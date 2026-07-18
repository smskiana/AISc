# Prompting 模块

本模块读取 `backend/config/prompt/` 中的任务规格、系统契约和标签规则，并将结构化上下文组装为 LLM `messages`。

业务逻辑只负责收集事实、候选项和既有 fallback，不应新增大段 Prompt 常量。新增 LLM 任务时先注册稳定的 `task_id` 与响应契约；只有确实需要机器解析的任务才声明结构化输出，并保持 Prompt 中的字段约束最短。角色和地点标签优先放在 profile/config 中。
