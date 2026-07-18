> 设计方案: [2026-07-16_AI诊断钩子强制同步规则_plan.md](2026-07-16_AI诊断钩子强制同步规则_plan.md)

# AI 诊断钩子强制同步规则 - 执行记录

## 实际改动

1. 在 `AGENTS.md` 核心行为底线新增“AI 诊断钩子同步（硬约束）”。
2. 强制 AI 调试 Unity 运行时功能时优先使用 `aisc_debug` 的结构化状态，而不是只解析零散日志。
3. 强制新增或修改功能时同步评估关键状态、阶段、失败原因和关联 ID 的诊断覆盖。
4. 业务语义变化时必须同步更新诊断 DTO、provider、MCP action、测试和入口文档。
5. 功能本体与诊断钩子未同步完成或未验证时，不得宣称完成。
6. 对确实不适用诊断钩子的改动，要求在 execution 中明确说明原因。

## 回写入口

- `AGENTS.md`
- `docs/Workstreams/ProjectGovernance/README.md`
- `docs/AIChanges/TestingAndDiagnostics/README.md`

## 验证方式

1. 使用 `rg` 确认“AI 诊断钩子同步”硬约束可从 `AGENTS.md` 直接命中。
2. 检查项目治理 Workstream 与测试诊断入口保持同一口径。
3. 检查 plan / execution 互相索引和 Markdown 路径。

## 诊断钩子适用说明

本轮只修改项目治理文档，不改变 Unity 运行行为，因此无需修改 `aisc_debug` 代码或运行时 DTO；已按新增规则明确记录不适用原因。

