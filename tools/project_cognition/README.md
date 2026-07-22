# Project Cognition

独立的项目认知 MCP Server 与 VS Code 薄适配器。Server 通过标准 MCP 客户端只读调用 codebase-memory，将代码事实转换为语言无关符号，并以签发范围约束 preview / apply。

## 架构边界

- `src/domain`：语言无关快照与关系模型。
- `src/scope`：Requested / Resolved / Evidence / Mutation 四层范围与预算。
- `src/update`：preview / apply 原子事务和并发检查。
- `src/query`：主要关系、关系证据和 revision freshness 查询。
- `src/governance`：功能域确认、人工归属、人工摘要和建议拒绝。
- `src/adapters/code-graph`：codebase-memory 公开 MCP 适配器。
- `src/adapters/snapshot-store`：项目本地 JSON 原子快照与上一版本回滚点。
- `src/adapters/ai-semantics`：AI 建议证据白名单收口；当前使用确定性 fixture。
- `src/adapters/revision`：只读 Git revision provider，用于 scope 签发和 apply 前复核。
- `vscode-extension`：只调用本 MCP，不接触存储或 codebase-memory；入口、MCP 客户端、功能树、源码导航和 UML 面板分模块维护。

VS Code 扩展使用 esbuild 生成单文件 CommonJS bundle，只保留宿主内建的 `vscode` external。`npm run package` 会先运行 `verify:bundle`，拒绝残留的 MCP SDK 运行时依赖，避免 VSIX 安装成功但 extension host 激活失败。

IDE 当前上下文通过独立的 `filePath` 与 `symbolName` 字段传入。Server 使用精确图过滤签发符号，并冻结该符号集合供 preview / apply 使用；preview 不会重新运行自然语言搜索。`smoke:context` 使用真实 stdio 和 codebase-memory 验证该不变量。

## 构建与最低门禁

```powershell
cd tools/project_cognition
npm install
npm test
npm run smoke:codebase
npm run smoke:context
npm run smoke:overview
npm run smoke:uml
npm --prefix vscode-extension install
npm run package:vscode
```

## 接入 Codex

先构建，再运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/project_cognition/scripts/register-codex.ps1
```

也可以手工配置 stdio MCP：命令为 `node`，参数为本目录 `dist/src/server.js` 的绝对路径；环境变量 `CODEBASE_MEMORY_COMMAND` 指向 codebase-memory MCP 可执行文件。

Server 提供完整查询、局部更新、人工治理与回滚工具，并提供 `project-cognition://projects/...` 的功能域、符号、关系和当前快照只读资源。分类器上下文中的事实证据携带方法级符号与精确位置，IDE 证据项从同一记录生成 label 和源码导航。所有工具失败统一返回稳定 `error.code`、`message` 和可选 `details`。

未确认功能归属的已写入符号通过查询层派生的 `待归类` 节点展示。该节点和虚拟 reference memberships 不写入快照，因此不会绕过人工确认创建正式功能域；建立正式 membership 后，对应符号会自动退出该节点。

## VS Code

安装 `vscode-extension/*.vsix` 后，活动栏出现 Project Cognition。编辑器标题栏的类型层级图标会读取当前文件的第一个类，并打开该类所属功能域的 UML；同一位置的同步图标继续执行 `Update Current Context`。扩展通过 stdio 启动同一个 MCP Server，使用 Dagre 布局分层类 UML 认知图；功能域节点按层下钻，类节点进入一跳中心图，继承、实现、调用和依赖使用不同箭头或线型，关系可展开事实证据，双击类可跳转源码。树和 UML 分类器层只显示类、接口、结构体、枚举或 record，方法只进入关系证据。局部更新先展示可变更范围、只读证据、排除项和差异，再显式确认 apply；全面更新使用独立命令和确认文本。

## 当前限制

第一轮只验证 AISc 的 C# / Python 索引、确定性 AI fixture 和本地单用户快照。真实模型、多仓库、团队同步与后台自动扫描不在本轮范围内。
