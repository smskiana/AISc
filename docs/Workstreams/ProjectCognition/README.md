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

阶段 A/B 的自动化、真实 codebase-memory smoke、Codex MCP 实际加载和 VSIX 构建已通过独立测试。Y08/Y09 的关系点击和 tooltip 已通过真实宿主复测；随后用户复核发现方法 evidence 的 label 与导航载荷不同源，`Start -> Load` 会退化为整个 Class。当前 classifier context 已返回带文件和行号的 Method symbols，证据选择明确导航调用方方法，并由真实 smoke 锁定 Method 位置。当前状态是“AB02 修复完成，待原 test 继续有界复测”；阶段 C 还需处理 AA09、AA13、40 节点和最长名称门禁。

## 下一阶段

1. 在原 test 复测 AB02：选择 `Start -> Load` 后必须精确定位 `GameManager.Start` 方法范围。
2. 继续修复和复测 AA09 多类文件首类确定性、AA13 关系键盘焦点、40 节点预算与最长名称 fixture。
3. 在新 Codex 任务复核真实 `RELATION_NOT_FOUND` contract；测试通过前复杂任务整体仍不得认定完成。
4. 阶段 A-C 全部通过后，再评估真实 AI Semantics Adapter；阶段 D 另开 plan。

## 相关入口

1. `tools/project_cognition/README.md`
2. `docs/AIChanges/ProjectGovernance/2026-07-22_IDE_MCP项目认知图工具_plan.md`
3. `docs/AIChanges/ProjectCognition/README.md`
4. `docs/AIChanges/ProjectCognition/2026-07-22_IDE_MCP项目认知图工具_test.md`
