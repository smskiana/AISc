# 后端 LLM 硬 Token 上限清理执行记录

> 设计方案: [2026-07-16_后端LLM硬Token上限清理_plan.md](2026-07-16_后端LLM硬Token上限清理_plan.md)

## 实际改动

1. 清理 `backend/src/` 内全部 12 处玩家对话、摘要、回复建议、记忆提取、记忆融合、图路由、NPC 计划、社交决策、印象刷新和 NPC-NPC 对话的 `max_tokens` 参数。
2. 移除 `NPC_MAX_TOKENS_PER_TURN` 及 NPC 对话模块中过期的硬 token 预算说明。
3. 保留现有 Prompt 对对白字数、对话轮数、候选数量、计划条目数、摘要句数和 JSON 格式的软约束。
4. 保留所有既有解析、字段截断、候选裁剪、合法性校验和失败兜底逻辑。
5. 同步 Dialogue、Memory、NpcBehavior Workstream 与代码目录 README。

## 诊断钩子检查

本次统一改变 LLM 调用预算口径，但不改变业务阶段、协议、关联 ID、控制动作或诊断 DTO 字段。现有日志与诊断仍覆盖调用结果、解析失败及业务失败；不再存在需要暴露的调用级硬 token 预算，因此无需修改 `aisc_debug` 或 `aisc_control`。

## 验证

1. `rg -n "max_tokens\\s*=" backend/src` 无命中。
2. `python -m compileall -q backend/src` 通过。
3. 后端全量 `unittest`：43 项通过。
4. 相关 Prompt 仍包含现有字数、句数、条目数、轮数和 JSON 格式软约束。

## 问题与处理

最初范围只包含玩家正式对话正文；用户随后明确要求清理其他所有硬上限，因此按扩展范围创建统一 plan，并在同一对话上下文仍可可靠追踪的前提下继续执行。早先的局部 execution 已回链到本记录。

## 未完成项

无。
