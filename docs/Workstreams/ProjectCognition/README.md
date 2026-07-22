# 工作流：项目认知工具

## 当前目标

用独立 MCP Server 把 codebase-memory 代码事实转换为可查询、可审计且受范围约束的项目认知，并由 Codex 和 VS Code 复用同一接口。

## 当前工程口径

1. 核心入口是 `tools/project_cognition/README.md`。
2. Server 通过公开 stdio MCP 客户端只读调用 codebase-memory，不读取其私有图数据库。
3. 更新必须经过 resolve -> preview -> apply；MutationScope 必须是 ResolvedScope 子集。
4. 普通更新不能升级为全项目更新；全面更新和回滚都有独立确认文本。
5. VS Code 是首个 IDE adapter，只调用 Project Cognition MCP，不直接访问快照或 codebase-memory。
6. Codex 通过本机 `mcp_servers.aisc-project-cognition` stdio 配置接入。
7. 本地快照位于 `.project-cognition/`，不进入 Git。

## 当前状态

阶段 A/B/C 的第一轮实现已完成执行期最低门禁：查询、范围更新、人工治理、只读资源、revision 复核和 VS Code 交互闭环均已落地。当前状态是“实现完成，待独立测试”；真实 AI 模型、团队同步、后台扫描、多仓库与第二 IDE 仍不在本轮范围。

## 下一阶段

1. 在独立测试会话覆盖范围不变量、revision 过期、并发冲突、回滚、真实 MCP contract 和 VS Code 宿主交互，并创建同主题 `_test.md`。
2. 对 VS Code 功能树、关系展开、长名称、窄窗口和大节点数量执行截图验收。
3. 在固定事实与确定性 fixture 通过独立测试后，再评估真实 AI Semantics Adapter；阶段 D 另开 plan。

## 相关入口

1. `tools/project_cognition/README.md`
2. `docs/AIChanges/ProjectGovernance/2026-07-22_IDE_MCP项目认知图工具_plan.md`
3. `docs/AIChanges/ProjectCognition/README.md`
