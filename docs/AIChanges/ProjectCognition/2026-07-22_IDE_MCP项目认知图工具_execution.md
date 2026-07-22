> 执行案：[2026-07-22_IDE_MCP项目认知图工具_plan.md](../ProjectGovernance/2026-07-22_IDE_MCP项目认知图工具_plan.md)
>
> 独立测试记录（当前失败，待继续有界复测）：[2026-07-22_IDE_MCP项目认知图工具_test.md](2026-07-22_IDE_MCP项目认知图工具_test.md)

# IDE + MCP 项目认知图工具执行记录

## 1. 执行结论

首轮实现进入独立测试后，阶段 C 先后暴露 VSIX 激活、源码跳转、范围约束、预览审计、Apply 后认知不可达、类 UML 主视图缺失及真实宿主关系交互问题。对应执行会话均已完成根因修复；当前结论是“Y08/Y09 修复完成，待原 test 继续有界复测”，复杂任务整体仍不得认定通过。

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

## 6. 独立测试失败修复

### 6.1 失败证据与根因

1. 独立测试记录 T07/T08 显示功能树没有 data provider，所有扩展命令均 not found。
2. VS Code extension-host 日志明确报错 `Cannot find module '@modelcontextprotocol/sdk/client/index.js'`，require stack 指向已安装扩展的 `dist/extension.js`。
3. 已安装 VSIX 使用 `--no-dependencies`，包内没有 `node_modules/@modelcontextprotocol/sdk`；同时原 `dist/extension.js` 保留对该包的运行时 `require`。因此扩展模块在调用 `activate()` 前加载失败，TreeDataProvider 与命令注册代码均没有执行。

### 6.2 实际修复

1. VS Code 扩展构建改为 esbuild 单文件 CommonJS bundle，只将宿主内建 `vscode` 标为 external；保留 `tsc --noEmit` 类型门禁。
2. 新增 `scripts/verify-bundle.mjs`，强制检查 bundle 包含运行时依赖、不残留 `@modelcontextprotocol` 外部 require，并保留 `vscode` external。
3. VSIX 继续使用 `--no-dependencies`，但入口现已自包含 MCP SDK；修复包已由 `code --install-extension --force` 覆盖安装。
4. `expand_relation_evidence` 对不存在的 relation ID 改为稳定 `RELATION_NOT_FOUND`，并补充 query 与真实 stdio contract 回归。

### 6.3 修复期最低门禁

1. `npm test`：11 tests，11 pass；stdio contract 已断言 `RELATION_NOT_FOUND`。
2. `npm run package`：类型检查、bundle、`verify:bundle` 和 VSIX 打包通过；bundle 为 577,558 bytes。
3. 安装产物检查：`HasUnresolvedMcpRequire=False`、`HasVscodeExternal=True`。
4. `npm run smoke:codebase`：继续成功定位 `GameManager.Awake`。
5. 用户协助执行真实 VS Code 宿主冒烟：Project Cognition 视图可打开，`Find Symbol` 可显示 `GameManager.Awake` 查询结果，`Update Current Context` 可进入范围预览确认框；原 provider/command not found 失败已不再复现。
6. 完整阶段 C 复测仍需在原 `_test.md` 追加；本执行记录不修改既有失败结论。

## 7. R06-R09 致命缺陷修复

### 7.1 根因

1. codebase-memory 已返回 `GameManager.Awake` 的 `start_line: 65`，但 Code Graph Adapter 转换时丢弃位置；VS Code 只打开文件，不设置 selection，因此光标停留在文件旧位置。
2. IDE 把文件路径作为 BM25 自然语言查询，未结构化传递当前文件和光标符号。`NpcSpawner.cs` 路径查询可产生 881 个候选，默认预算裁剪后自然固定为 30。
3. resolve 签发 scope 后，preview 又使用更大 limit 重新搜索，实际预览集合没有冻结为已签发的符号对象，存在范围漂移风险。
4. VS Code 确认框只显示计数，没有消费目标域、具体符号、排除域和预算等结构化明细。

### 7.2 实际修复

1. `CodeSymbol` 增加 analyzer source location；codebase-memory adapter 保留 `start_line/end_line`，VS Code 通过 `showTextDocument` selection 跳转并居中显示准确范围。
2. VS Code 使用 document symbol provider 获取光标处最内层符号，并将 `symbolName` 与仓库相对 `filePath` 分字段传给 Server。
3. codebase-memory adapter 对 IDE 上下文使用精确 `name_pattern + file_pattern`；普通责任搜索仍保留 BM25。
4. Server 保存签发时的具体 `CodeSymbol[]`，preview 只消费该集合，不再二次调用图搜索。
5. 新增独立 `scope-view`，返回目标域、包含符号、只读证据、排除符号、排除域，以及文件/符号/关系预算；VS Code 确认框展示具体名称和成本。
6. 新增真实 stdio `smoke:context`，锁定不同文件/符号的精确范围与 resolve-to-preview 稳定性。

### 7.3 修复期最低门禁

1. `npm test`：13 tests，13 pass；新增 source location 与 scope view 回归。
2. `npm run smoke:codebase`：`GameManager.Awake` 返回 `startLine=65`、`endLine=130`。
3. `npm run smoke:context`：`GameManager` 与 `NpcSpawner` 均只签发 1 个对应符号，preview 各保持 1 个相同 change。
4. VS Code 类型检查、bundle、`verify:bundle` 与 VSIX 打包通过；修复版 VSIX 已覆盖安装。
5. 真实宿主 R06-R09 复测仍须在原 `_test.md` 追加，本执行记录不修改失败结论。

## 8. Apply 后认知不可达修复

### 8.1 根因

1. 第二次复测确认 Apply 已持久化符号，但快照没有正式 domains / memberships；这符合探索范围不能自动创建正式功能域的不变量。
2. `get_domain_overview` 只返回有 membership 的符号，VS Code 功能树又完全依赖该结果，导致未归属符号虽然已写入快照却无法从 IDE 到达。
3. 缺陷位于查询投影，不在 Snapshot Store 原子提交；修复不能通过自动创建正式域或正式 membership 绕过人工确认。

### 8.2 实际修复

1. 新增独立 `domain-overview` 查询模块，为没有任何 membership 的持久化符号派生稳定 `virtual:unclassified` 节点，显示名为 `待归类`。
2. 派生节点状态为 `proposed`，符号使用非持久化 `reference` membership；原 ProjectSnapshot 不发生任何写入。
3. 一旦符号获得正式 membership，它会自动退出 `待归类`，不产生重复实体。
4. `get_domain_overview`、domains/domain 只读资源和虚拟域主要关系查询统一复用该投影口径。
5. 新增真实 `smoke:overview`，直接验证当前本地快照在 `domains=0 / memberships=0` 时仍可展示 61 个符号，并断言投影不修改快照。

### 8.3 修复期最低门禁

1. `npm test`：15 tests，15 pass；新增待归类投影、全归属时隐藏虚拟域和虚拟域关系聚合回归。
2. `npm run smoke:overview`：`persistedDomains=0`、`persistedMemberships=0`、`visibleSymbols=61`。
3. `npm run smoke:context`：精确上下文与 resolve-to-preview 稳定性继续通过。
4. VS Code 类型检查、bundle、产物门禁和 VSIX 打包安装通过。
5. 真实宿主功能树、关系入口与大节点数量仍须在原 `_test.md` 追加复测。

## 9. 类 UML 主视图补齐与扩展减重

### 9.1 缺口与根因

1. 原 VS Code adapter 只有功能树与关系表 Webview，没有按 plan 实现分层 UML 主视图、类中心一跳图和差异化关系箭头。
2. `extension.ts` 同时承担 MCP 生命周期、树数据、命令、源码导航、更新流程和 Webview，继续直接加入图渲染会扩大多职责类。
3. execution 曾把“关系可查询”错误等同于“阶段 C 展示形态已实现”，缺少针对 UML 结构的产物门禁。

### 9.2 实际修复

1. 按用户“先减重，再补齐类 UML”指令拆出 `cognition-client`、`domain-tree`、`symbol-navigation`、`uml/graph-layout` 与 `uml/uml-panel`；`extension.ts` 收缩为组合入口和更新命令。
2. 引入 `@dagrejs/dagre` 成熟布局库，固定节点尺寸和 40 节点 / 80 关系预算，不手写布局算法，也不隐式展开全项目。
3. 功能域视图只展示直属子域和直属类；功能域节点下钻并提供面包屑返回，类节点进入一跳中心图。
4. 类节点只展示类名、类型、职责摘要和状态；继承、实现、调用、依赖分别使用实线/虚线及三角/箭头组合，语义不只依赖颜色。
5. 关系点击展开事实证据；选择可定位的证据后跳转源码，双击类节点直接打开 analyzer 行号范围。
6. UML Webview 保持 VS Code 主题色、固定节点尺寸、长文本截断与完整 tooltip；搜索到但尚未持久化的符号以只读种子进入类中心图，不写认知快照。
7. VSIX manifest、bundle 门禁和工具 README 已同步更新；原 `showRelations` 命令保留兼容并路由到 UML 面板。

### 9.3 实现期最低门禁

1. Project Cognition Server `npm test`：15 tests，15 pass。
2. VS Code graph layout `npm test`：2 tests，2 pass，覆盖 Dagre 非重叠布局和四类事实关系映射。
3. VS Code `tsc --noEmit`、esbuild 自包含 bundle 和 `verify:bundle` 通过；bundle 门禁确认 UML panel 与 relation marker 存在。
4. VSIX 打包成功，产物 133.76 KB，已使用 `code --install-extension --force` 覆盖安装。
5. 本会话不修改原 `_test.md` 结论；真实 Extension Host、窄窗口、长名称、40 节点上限与图交互截图必须在独立测试会话验收。

## 10. 当前文件功能域 UML 入口修正

### 10.1 用户确认的入口语义

1. UML 入口必须位于编辑器标题栏，与 `Update Current Context` 同一区域，而不是要求用户先在左侧功能树选择节点。
2. 点击后以当前文件为上下文；若文件声明多个类，不猜测光标意图，按文档符号遍历顺序取第一个类。
3. 打开的起点是该类所属功能域 UML；当前文件是该功能域图的一部分，用户再从图中继续探索。

### 10.2 实际修复

1. 新增 `projectCognition.openCurrentUml` 编辑器标题栏命令，使用类型层级图标；`Update Current Context` 使用同步图标并与其相邻。
2. 新增首类解析：遍历 VS Code document symbols，确定性选择第一个 `SymbolKind.Class`。
3. `find_symbol` 增加可选 `filePath` / `symbolName`，通过 codebase-memory 的精确名称和文件过滤定位当前类，不使用宽泛 BM25 猜测。
4. 功能域解析优先类自身 primary membership，其次同文件已知符号 membership，最后使用非持久化 `待归类`；临时 reference 只存在于当前视图，不写快照。
5. 功能树和 UML 当前层只展示 class / interface / struct / enum / record，方法继续保留为关系证据。
6. Tree item 行内命令全部配置主题图标和精确 `viewItem` 条件，消除完整命令标题挤占树行的问题。

### 10.3 实现期最低门禁

1. VS Code adapter：4 tests，4 pass；新增当前文件 membership 优先级、同文件继承和 `待归类` fallback 回归。
2. Project Cognition Server：15 tests，15 pass；TypeScript 编译通过。
3. 真实 codebase-memory 精确查询 `WebSocketClient + Assets/Scripts/Core/WebSocketClient.cs` 唯一命中 `Class`。
4. VSIX bundle / marker 门禁与打包通过，产物 134.73 KB，并已覆盖安装。
5. 当前文件标题栏点击、真实功能域起点和图内探索仍须在原独立测试记录中验收。

## 11. 第三次复测 U08 / U10 修复

### 11.1 失败证据与根因

1. U08 在真实 `WebSocketClient.cs` 上提示没有类；C# 扩展返回扁平 `SymbolInformation[]`，原实现只有对象带 `children` 时才检查 `SymbolKind.Class`，因此跳过所有扁平类。
2. U10 从 `待归类` 打开 UML 后为空；当前快照的 61 个符号来自旧的局部方法更新，没有持久化 Class。UML 正确过滤方法后没有分类器，同时域视图没有按方法所属文件回查类。
3. 原 4 项单测只覆盖 membership 选择和纯图布局，没有覆盖 VS Code 两种 document symbol 形态，也没有真实验证“方法 membership -> 文件 Class”投影。

### 11.2 实际修复

1. 首类识别改为同时处理扁平 `SymbolInformation` 和嵌套 `DocumentSymbol`，仍按返回顺序确定性选择第一个 Class。
2. `find_symbol` 增加受限 `kind` 参数，Code Graph Adapter 将其映射为 codebase-memory `search_graph.label`；当前文件入口使用 `filePath + exact symbolName + Class`。
3. UML 打开功能域时检查直属 membership；若成员只有方法，则按去重文件路径、40 节点预算并行查询 Class，并添加只存在于当前视图的 reference membership。
4. Class 投影不修改 `.project-cognition` 快照；旧方法仍只用于证据和反查文件，不重新进入分类器节点。
5. 新增 `smoke:uml`，通过正式 stdio Server、公开 codebase-memory MCP 和当前真实快照验证旧状态可生成类节点。

### 11.3 实现期最低门禁

1. VS Code adapter：6 tests，6 pass；新增扁平 `SymbolInformation` 与嵌套首类顺序回归。
2. Project Cognition Server：15 tests，15 pass；TypeScript 编译通过。
3. `npm run smoke:uml`：通过，当前 3 个待归类成员文件解析出 4 个 Class。
4. VSIX bundle 与 marker 门禁通过，打包产物 135.17 KB，并已覆盖安装。
5. 本执行会话不改写 `_test.md`；U08、U10、U11 和真实视觉预算仍须在原测试记录继续有界复测。

## 12. 第四次复测 V04-V06 修复

### 12.1 反馈闭环与根因

1. V04/V05 证明真实宿主缺少 C# Dev Kit，`vscode.executeDocumentSymbolProvider` 返回空；前一轮只兼容 provider 的两种返回形态，没有覆盖 provider 完全不可用。
2. V06 的正式 stdio smoke 已证明 4 个 Class 可解析，因此继续检查最终 bundle。产物明确显示 `full.textContent=node.title+'` 后直接换行，生成的 Webview JavaScript 字符串未闭合。
3. Webview 在脚本执行前已渲染静态返回按钮，因此真实现象正是“只有返回按钮、没有面包屑和节点”；根因与宿主证据完全吻合。

### 12.2 实际修复

1. 当前文件入口将 IDE document symbol provider 改为可选优化；返回空时直接以 `filePath + kind=Class` 查询公开 codebase-memory MCP。
2. 多类文件的降级结果按 analyzer `startLine` 升序、qualified name 稳定排序，继续满足“第一个到达的类”口径。
3. UML tooltip 换行改为双层转义，确保生成后的 Webview 脚本保留 `\\n` 字面量而不是嵌入源码换行。
4. `verify:bundle` 新增失败模式门禁：拒绝 `full.textContent` 后出现实际换行，并要求 bundle 中存在正确转义序列。

### 12.3 实现期最低门禁

1. VS Code adapter：7 tests，7 pass；新增 code graph fallback 按 `startLine` 取首类回归。
2. Project Cognition Server：15 tests，15 pass。
3. 首次执行新 bundle 门禁时成功拦截错误的转义断言；按最终产物字节修正门禁后，bundle 655,313 bytes 并通过。
4. VSIX 打包成功，产物 135.2 KB，已覆盖安装。
5. 本执行会话不修改原 `_test.md`；真实 V04-V08 与视觉截图仍须在原测试记录继续有界复测。

## 13. 第五次复测 W06 路由修复

### 13.1 根因

1. W05 证明当前文件 Class 已能通过 code graph 定位，W07 证明 UML 数据投递和 Webview 渲染均已恢复。
2. 当前文件命令完成 membership 解析后调用 `uml.show(resolution.domainId, ...)`，所以实现必然把“待归类”功能域作为首屏 focus。
3. 用户要求当前文件是 UML 探索起点；所属功能域应作为导航上下文，而不是替代当前类中心图。

### 13.2 实际修复

1. `CurrentDomainResolution` 新增明确 `focusId`，固定为当前文件首类 symbol ID；`domainId` 继续用于只读 membership 和 breadcrumb。
2. 当前文件命令改为 `uml.show(resolution.focusId, ...)`，因此首屏标题为当前类，面包屑仍可返回所属功能域。
3. bundle 门禁新增当前文件路由断言，若重新使用 domain-only focus 则打包失败。

### 13.3 实现期最低门禁

1. VS Code adapter：7 tests，7 pass；membership 测试同时断言 domain ID 与 class focus ID。
2. Project Cognition Server：15 tests，15 pass。
3. bundle 655,332 bytes，Webview 转义、UML marker 和 current-file class focus 门禁全部通过。
4. VSIX 打包成功，产物 135.21 KB，已覆盖安装。
5. 本执行会话不改写 `_test.md`；W06-W09 仍须在原测试记录继续有界复测。

## 14. 第六次复测 X07 / X08 修复

### 14.1 根因与图谱证据

1. X07 中 Class 可打开文件但落到第 1 行；`search_graph` 的 Class 结果没有 `start_line`，`openSymbolLocation` 因此使用默认行。
2. 公开 `get_code_snippet` 对同一 qualified name 稳定返回 `start_line=17 / end_line=408`，证明位置事实可从受支持 MCP seam 补齐。
3. X08 的 Class `trace_path` 为空，但图中存在 `Class -> DEFINES_METHOD -> Method -> CALLS -> Method <- DEFINES_METHOD <- Class`；当前类中心图只查认知快照语义，遗漏公开代码图事实。
4. 对 `WebSocketClient` 的限定图查询得到 `ProtocolClient`、`MessageRouter`、`UnitySaveService` 等类关系，因此“无边”不是代码事实。

### 14.2 实际修复

1. Code Graph Adapter 对缺少位置的分类器最多并行补取 20 个公开 snippet，只合并行号，不读取私有图存储。
2. 新增 `get_classifier_context` MCP 工具，使用受限、只读 `query_graph` 聚合方法 CALLS 为类到类关系，过滤类内自调用并按证据数排序。
3. 类中心 UML 合并 classifier context 的临时类节点、关系和方法 qualified-name 证据；这些内容不写入认知快照。
4. 关系点击优先使用当前图的临时证据，仍可从证据项跳转已知类源码；快照关系继续使用原 `expand_relation_evidence`。
5. `smoke:uml` 扩展为同时锁定类位置和一跳关系，避免再次只证明“能查到类”。

### 14.3 实现期最低门禁

1. VS Code adapter：7 tests，7 pass；Project Cognition Server：15 tests，15 pass。
2. `npm run smoke:uml`：`memberFiles=3`、`classifiers=4`、`classStartLine=17`、`relations=6`。
3. stdio contract 已登记 `get_classifier_context`；VSIX bundle 656,307 bytes，全部门禁通过。
4. VSIX 打包成功，产物 135.39 KB，已覆盖安装。
5. 本执行会话不修改原 `_test.md`；X07-X09、关系证据点击和视觉截图仍须在原测试记录继续有界复测。

## 15. Y08 / Y09 关系交互修复

### 15.1 根因

1. 原 Webview 只给 1.5px SVG 可见 path 绑定 click，鼠标命中困难；关系 label 是独立 text，没有事件。
2. CSS hover 只改变线条颜色，没有原生 `<title>` 或自定义 tooltip，因此悬停只能看到高亮。
3. bundle 门禁只验证关系 marker 存在，没有验证关系是否可点击或是否提供可见说明。

### 15.2 实际修复

1. 每条关系改为统一 `edge-group`，包含可见线、14px 透明 `edge-hit` 和 label；整组共享 evidence handler。
2. 线条命中区、标签和键盘 Enter/Space 都发送同一个 `{command: evidence, id}` 消息。
3. 新增 VS Code 主题化自定义 tooltip，pointer enter/move 时显示关系摘要、kind、status 和 evidence count，离开时隐藏。
4. bundle 门禁新增 `edge-hit`、共享 `openEvidence` 和 `edge-tooltip` 断言。

### 15.3 实现期最低门禁

1. VS Code adapter：7 tests，7 pass；Project Cognition Server：15 tests，15 pass。
2. VSIX bundle 657,728 bytes，关系命中与 tooltip 门禁通过。
3. VSIX 打包成功，产物 135.75 KB，已覆盖安装。
4. 本执行会话不修改原 `_test.md`；Y08/Y09 必须在原测试记录继续有界复测。

## 16. AB02 方法级证据导航修复

### 16.1 根因

1. 第八次复测只证明证据项能返回源码，没有验证落点是否为证据 label 对应的方法；用户复核确认 `Start -> Load` 实际回到整个 `GameManager` Class。
2. 临时 classifier context 的 evidence 复用了类关系两端的 Class ID；QuickPick label 虽使用 Method qualified name，导航载荷却从 Class ID 查找 `SymbolRecord`，展示与行为不一致。
3. codebase-memory 的 Method 节点已公开提供 `file_path/start_line/end_line`，缺陷位于 Project Cognition 的查询投影，不是分析器缺少位置事实。

### 16.2 实际修复

1. `get_classifier_context` 查询同时返回调用方和被调 Method 的文件与位置，并把 Method 作为独立 `CodeSymbol` 返回。
2. 每条临时 CALLS evidence 的 `sourceSymbolId/targetSymbolId` 改为对应 Method ID；聚合关系的两端仍保持 Class ID，因此 UML 图结构不变。
3. VS Code adapter 新增纯映射模块，使 evidence label、说明路径和导航对象来自同一条方法证据；当前交互明确跳转调用方方法。
4. 新增 `Start -> Load` 回归，断言选择项导航到 `GameManager.Start` 的精确位置，而不是包含它的 Class。

### 16.3 实现期最低门禁

1. VS Code adapter：8 tests，8 pass；Project Cognition Server：15 tests，15 pass。
2. `npm run smoke:uml`：`relations=6`，首条 evidence 的 source symbol 为带位置的 Method，`evidenceMethodStartLine=93`。
3. VSIX bundle 657,938 bytes，打包成功并已使用 `--force` 覆盖安装。
4. 本执行会话不修改原 `_test.md`；AB02 必须在原测试记录继续有界复测，复杂任务仍未完成。
