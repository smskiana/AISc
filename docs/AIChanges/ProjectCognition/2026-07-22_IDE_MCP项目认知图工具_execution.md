> 执行案：[2026-07-22_IDE_MCP项目认知图工具_plan.md](../ProjectGovernance/2026-07-22_IDE_MCP项目认知图工具_plan.md)
>
> 测试记录（后续独立测试会话创建）：[2026-07-22_IDE_MCP项目认知图工具_test.md](2026-07-22_IDE_MCP项目认知图工具_test.md)

# IDE + MCP 项目认知图工具执行记录

## 1. 执行结论

实现完成，待独立测试。首个 IDE 已按用户确认选择 VS Code；MCP Server 使用标准 stdio，由 Codex 和 VS Code 复用。plan 第一轮阶段 A/B/C 的实现缺口已补齐，本执行会话不创建 `_test.md`，下一独立测试会话按 plan 验收标准正式验收。

## 2. 实际改动

1. 新增 `tools/project_cognition/` 独立 TypeScript 包，包含语言无关领域模型、四层范围引擎、preview/apply 服务、原子 JSON 快照与上一版本回滚。
2. 新增 codebase-memory 公开 MCP 客户端适配器；未读取或依赖其私有数据库 schema。
3. 新增确定性 AI semantics fixture 收口，未知 evidence ID 整批拒绝。
4. 新增标准 stdio MCP Server，提供 `find_symbol`、`get_domain_overview`、`get_symbol_context`、`resolve_update_scope`、`preview_scoped_update`、`apply_scoped_update`、`request_full_update` 和 `rollback_snapshot`。
5. 新增 VS Code 薄扩展，提供功能域树、符号搜索和源码跳转；已打包并安装 `aisc-local.aisc-project-cognition-vscode@0.1.0`。
6. 已在本机 Codex 配置中注册 `aisc-project-cognition` stdio MCP，下一次任务启动时加载。
7. 新增 ProjectCognition Workstream 和 AIChanges 功能目录，并回写 ProjectIndex、Roadmap、ChangeIndex 与 ProjectGovernance 路由。
8. 补齐 `get_primary_relations`、`expand_relation_evidence`、`check_scope_freshness` 和四个人工治理工具；新增五类只读资源 URI。
9. 所有 MCP 工具失败统一返回稳定结构化错误对象；scope 签发记录 Git revision，preview/apply 前重新读取并拒绝过期 revision。
10. VS Code adapter 补齐多层功能树、中央关系视图、点击展开证据、状态展示、当前上下文局部更新、范围/差异确认和独立全面更新命令。
11. 修正正式 server 产物入口为 `dist/src/server.js`，同步 npm bin、启动命令、注册脚本、VS Code 默认配置和本机 Codex 配置，并覆盖安装新 VSIX。

## 3. 最低门禁

1. `npm test`：TypeScript 编译通过，11 个范围预算、跨域只读、全面更新确认、revision 过期、证据白名单、人工治理、关系证据、结构化错误、并发快照和真实 stdio MCP contract 测试全部通过。
2. `npm run smoke:codebase`：通过公开 MCP seam 查询 AISc，成功定位 `GameManager.Awake` 和 `Assets/Scripts/Core/GameManager.cs`。
3. VS Code extension TypeScript 编译通过，VSIX 打包成功并由 `code --install-extension --force` 覆盖安装成功。
4. 本轮未运行 Unity、游戏后端或长跑工具，因为实现完全位于独立开发工具目录，不修改游戏运行时；该选择符合 TestingAndDiagnostics Workstream。

## 4. 方案审查与偏差

1. codebase-memory 接入探针成立，因此未触发回到方案会话的停止条件。
2. Snapshot Store 第一轮选择原子 JSON 文件而非 SQLite，通过 adapter 隔离，满足 plan 允许的等价嵌入式存储口径。
3. 阶段 B 仍使用确定性 fixture 与证据白名单；真实模型按 plan 在固定事实与边界通过独立测试后再评估，不属于本轮缺口。
4. codebase-memory canonical 索引配置排除 `tools/`，所以工具自身未进入项目图；已用公开 MCP 的真实 smoke 和独立 stdio contract 覆盖接入可行性。
5. Snapshot Store 继续使用 adapter 隔离的原子 JSON；Git revision provider 只读调用 `git rev-parse HEAD`，不改变仓库状态。

## 5. 未完成与独立测试范围

1. 当前 Codex 任务不会动态重载新 MCP 配置；配置路径已修正且 stdio contract 已通过，需在下一新任务确认 Codex 实际工具枚举。
2. VS Code 宿主内的功能树、关系点击、长名称、窄窗口和大节点渲染尚未执行桌面截图验收，留给独立测试会话。
3. 真实 AI Semantics Adapter、阶段 D 的多语言 analyzer、多仓库和第二 IDE 明确不在第一轮范围。
4. 本轮不创建 `_test.md`；复杂任务整体是否通过必须由下一独立测试会话判定。
