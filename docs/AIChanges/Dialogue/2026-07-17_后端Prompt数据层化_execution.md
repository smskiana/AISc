> 设计方案: [2026-07-17_后端Prompt数据层化_plan.md](2026-07-17_后端Prompt数据层化_plan.md)

# 后端 Prompt 数据层化执行记录

## 实际改动

- 新增 `backend/config/prompt/` 与 `backend/src/prompting/`，覆盖计划中的 10 个 task。
- Dialogue、NPC 行为、夜间印象、记忆提取/融合/路由改为提交结构化上下文；解析、硬校验和 fallback 保留。
- 5 个 NPC profile 和 9 个主要地点 profile 增加轻量标签，旧字段未删除。
- 新增 Prompt 注册完整性、旧字段兼容和输出纪律测试文件。

## 诊断与控制钩子

未新增 `aisc_debug` DTO 或 `aisc_control` action。本轮只迁移 Prompt 渲染结构，不改变业务阶段、请求状态、检索快照或控制语义。`PromptAssembler` 记录 task、contract、上下文键、sections 和 message 数量，不记录完整 Prompt 正文。

## 验证

- `python -m compileall -q backend/src backend/tests`：通过。
- Python 直接加载并渲染全部 10 个 task：通过。
- Python 直接校验 5 个 NPC 的三类标签：通过；9 个地点均已补齐三类标签。
- `pytest` 不可用：当前环境无 pytest 命令，且 `python -m pytest` 报告未安装模块。
- 未执行真实 LLM 质量长测和 Unity Play Mode；按 plan 暂缓。

## 未完成项

1. 真实 LLM 长测、玩家对话完整链路和 Unity EditMode/Play Mode 尚未执行。
2. 业务文件中的旧 Prompt 常量仍保留为未使用兼容文本；当前运行入口已全部切换到数据层。
