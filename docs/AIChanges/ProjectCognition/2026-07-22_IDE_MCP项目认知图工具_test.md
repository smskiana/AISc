> 执行案：[2026-07-22_IDE_MCP项目认知图工具_plan.md](../ProjectGovernance/2026-07-22_IDE_MCP项目认知图工具_plan.md)
>
> 执行记录：[2026-07-22_IDE_MCP项目认知图工具_execution.md](2026-07-22_IDE_MCP项目认知图工具_execution.md)

# IDE + MCP 项目认知图工具独立测试记录

## 1. 测试结论

**第二次复测仍失败。** 阶段 A/B 的自动化、真实 codebase-memory 只读接入、Codex MCP 加载和 VSIX 构建通过；阶段 C 的宿主激活、源码跳转和当前上下文范围缺陷已确认修复，但 Apply 后快照没有形成可展示的功能域或归属，刷新后的功能树仍为空，已写入的符号与关系无法从 IDE 进入。复杂任务整体不得认定完成，必须回到新的执行会话修复后继续有界复测。

## 2. 测试环境

1. 仓库：`F:/GameProject/unity/AISc`
2. Git revision：`65bb01e16435ffe1d82487d7ab432df8e67bf453`
3. Project Cognition：`aisc-project-cognition@0.1.0`
4. VS Code 扩展：已安装 `aisc-local.aisc-project-cognition-vscode@0.1.0`
5. 代码图：codebase-memory 项目 `AISc`，测试时可读取 11,514 个节点和 27,069 条边。

## 3. 工具选择

1. 使用工具包自身的 `npm test`，覆盖确定性范围、更新、治理、错误结构和 stdio contract。
2. 使用 `npm run smoke:codebase`，验证公开 codebase-memory MCP seam 的真实只读接入。
3. 使用当前 Codex 任务加载的 Project Cognition MCP，验证客户端实际枚举和真实查询。
4. 使用 `npm run package:vscode`，验证扩展编译和 VSIX 打包。
5. 使用真实 VS Code 宿主进行人工交互验收；本工具不修改 Unity 运行时、场景或 Prefab，因此不选择 Unity MCP、PlayMode、`aisc_debug` 或后端长跑工具。

## 4. 结构化证据

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| T01 | 自动化 contract | `npm test`：11 tests，11 pass，0 fail | 通过 |
| T02 | 真实代码图接入 | `npm run smoke:codebase` 定位 `GameManager.Awake` 与 `Assets/Scripts/Core/GameManager.cs` | 通过 |
| T03 | Codex 客户端加载 | 当前任务实际枚举 15 个 Project Cognition MCP 工具 | 通过 |
| T04 | Codex 真实查询 | `find_symbol("GameManager.Awake")` 返回稳定 symbol ID、qualified name 和文件路径 | 通过 |
| T05 | VSIX 构建 | TypeScript 编译通过并生成 `aisc-project-cognition-vscode-0.1.0.vsix` | 通过 |
| T06 | VS Code 安装 | 扩展列表存在 `aisc-local.aisc-project-cognition-vscode` | 通过 |
| T07 | 功能域树激活 | 侧栏显示 `There is no data provider registered that can provide view data.`；重载窗口后仍复现 | 失败 |
| T08 | VS Code 命令注册 | Find Symbol、Refresh、Update Current Context 分别返回对应 command `not found` | 失败 |
| T09 | 不存在关系的错误契约 | `expand_relation_evidence` 传入不存在的 relation ID 返回 `{ "ok": true }`，未返回稳定 not-found 错误 | 疑点 |

## 5. 与验收标准的对应

1. 阶段 A：已由聚焦自动化、真实 smoke 和 Codex 实际 MCP 查询证明主要 contract 可运行；本次没有人工重放 plan 中全部状态组合，仍以自动化证据为主。
2. 阶段 B：证据白名单、人工治理和固定 fixture 的确定性测试通过；真实 AI Adapter 不在本轮范围。
3. 阶段 C：未通过。扩展已安装且贡献的 Activity Bar、视图标题和按钮可见，但扩展入口未成功注册 TreeDataProvider 与命令，核心 IDE 闭环不可用。

## 6. 阻断与未覆盖项

1. 必须在新执行会话诊断并修复 VS Code extension activation；测试会话不修改实现。
2. 修复后必须复测功能树多层展开、符号搜索、关系证据、源码跳转、当前上下文局部更新、范围/差异确认和独立全面更新命令。
3. 长名称、窄窗口、大节点数量及无重叠截图验收被激活失败阻断，尚未执行。
4. 需明确不存在的 relation ID 应返回空成功还是稳定 not-found 错误；当前行为与“所有工具失败返回稳定结构化错误”的执行口径存在疑点。
5. 本次未单独人工重放 plan 的全部 14 个必测场景，也未单独采集性能预算指标；后续复测应补齐与阶段 C 相关且未被自动化覆盖的证据。

## 7. 后续复测规则

修复必须进入新的执行会话并更新 execution 证据。复测仍属于同一主题时，在本文件追加有界复测记录；若实现边界或验收主题变化，则创建互链的新 test。

## 8. 有界复测：VSIX 运行时依赖修复后

### 8.1 复测环境与工具

1. 复测 revision 仍为 `65bb01e16435ffe1d82487d7ab432df8e67bf453`，工作树包含 execution 所述未提交修复。
2. 继续使用工具包自动化、真实 codebase-memory smoke、bundle 产物门禁和用户协助的真实 VS Code 宿主交互。
3. 截图证据：`C:/Users/HP/Pictures/Screenshots/屏幕截图 2026-07-22 111603.png`、`屏幕截图 2026-07-22 112406.png`、`屏幕截图 2026-07-22 112534.png`。

### 8.2 复测证据

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| R01 | 自动化 contract | `npm test`：11 tests，11 pass，0 fail；新测试断言 `RELATION_NOT_FOUND` | 通过 |
| R02 | VSIX bundle | `npm run package` 通过；`verify:bundle` 返回 577,558 bytes，仅 external `vscode` | 通过 |
| R03 | 真实代码图接入 | `npm run smoke:codebase` 再次定位 `GameManager.Awake` | 通过 |
| R04 | 扩展宿主激活 | Project Cognition 视图可用，原 provider/command-not-found 不再复现 | 通过 |
| R05 | 符号搜索与长名称 | `GameManager.Awake` 返回结果；长 qualified name 与路径使用可读省略，无重叠 | 通过 |
| R06 | 源码跳转 | `BubbleUI.Awake` 正确跳转；`GameManager.Awake` 错误落到 `OnNpcDailyScheduleReady` 字段而非约 65 行的 `Awake` | 失败 |
| R07 | 当前上下文局部更新 | 命令进入确认框，但只显示 `Mutable: 30`、`Read-only evidence: 0`、`Excluded: 0`、`Changes: 30` | 失败 |
| R08 | 局部预览完整性 | 未展示目标域、具体包含符号、排除域、跨域只读证据明细或预计成本 | 失败 |
| R09 | 当前上下文范围约束 | 用户对多个不同文件重复执行 `Update Current Context`，均固定得到 `Mutable: 30`、`Changes: 30`，结果不随当前文件或符号变化 | 失败 |
| R10 | 全面更新独立入口 | 独立命令要求输入精确确认文本 `FULL UPDATE AISc`；测试按 Escape 取消 | 通过 |
| R11 | 当前 Codex 实例错误契约 | 当前任务中的旧 MCP 进程仍返回旧 `{ok:true}`；新构建自动化已通过，需新 Codex 任务做真实加载复核 | 待复核 |

### 8.3 复测结论与剩余阻断

1. VSIX 缺少运行时 MCP SDK 导致的宿主激活故障已确认修复。
2. 阶段 C 仍未通过：源码跳转并非对所有返回符号可靠，局部更新预览不满足 plan 15.3.3 的信息完整性要求。
3. 跨文件重复出现固定 30 个可变更项，确认当前 IDE 文件/符号上下文没有正确约束解析结果，违反 plan 必测场景 3 和 MutationScope 范围口径。
4. 在范围明细可见且当前上下文能产生差异化、可解释的有界范围前，不执行 Apply，避免写入无法审计的扩大范围。
5. 功能树多层展开、关系证据、应用后状态、窄窗口和大节点数量仍未完成独立验收。
6. 必须进入新的执行会话修复 R06-R09；修复后继续在本文件追加有界复测。

## 9. 第二次有界复测：R06-R09 修复后

### 9.1 自动化与真实 seam

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| S01 | 自动化 contract | `npm test`：13 tests，13 pass，0 fail | 通过 |
| S02 | VSIX bundle | `verify:bundle` 返回 579,768 bytes，仅 external `vscode`；VSIX 打包成功 | 通过 |
| S03 | 源码位置 seam | `npm run smoke:codebase` 返回 `GameManager.Awake startLine=65, endLine=130` | 通过 |
| S04 | 当前上下文 seam | `npm run smoke:context`：GameManager 与 NpcSpawner 各签发 1 个对应符号，preview 各保持 1 个 change | 通过 |

### 9.2 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| S05 | `GameManager.Awake` 跳转 | 用户确认准确跳转并选中 65-130 行 | 通过 |
| S06 | 跨文件范围差异 | GameManager 与 NpcSpawner 预览各包含 1 个不同符号，不再固定为 30 | 通过 |
| S07 | 预览审计信息 | 弹窗显示 Target domain、Included symbols、Read-only evidence、Excluded symbols/domains、Estimated cost 和 Changes | 通过 |
| S08 | GameManager Apply | 审计范围为 1 file、1 symbol、1 change 后执行 Apply | 已执行 |
| S09 | Apply 后功能树 | Apply 后点击 Refresh，功能树仍为空 | 失败 |
| S10 | 快照持久化结构 | `.project-cognition/AISc.json` 存在且更新；含 61 symbols、1 fact relation、1 semantic relation，但 domains=0、memberships=0 | 失败 |
| S11 | 关系与证据入口 | 因功能树为空，无法从 IDE 进入已写入符号、主要关系或事实证据 | 阻断 |

截图证据：

1. `C:/Users/HP/Pictures/Screenshots/屏幕截图 2026-07-22 115144.png`
2. `C:/Users/HP/Pictures/Screenshots/屏幕截图 2026-07-22 115150.png`
3. `C:/Users/HP/Pictures/Screenshots/屏幕截图 2026-07-22 115450.png`

### 9.3 第二次复测结论

1. R06-R09 的源码位置、精确上下文、签发集合冻结和完整预览已确认修复。
2. 阶段 C 仍未通过：局部更新在 Exploration 范围内写入符号后，没有产生可展示的 proposed domain、membership 或等价的“待归类/探索”入口。
3. 当前快照已包含符号和关系，但功能树只依赖 domains/memberships，导致已持久化认知对 IDE 用户不可达，违反阶段 C 验收标准 15.3.1 和 15.3.2。
4. 修复前停止继续 Apply；新的执行会话需要明确探索结果如何进入功能树，同时保持“未经确认不创建正式功能域”的领域不变量。
5. 修复后继续复测功能树多层展开、主要关系、证据展开、源码跳转、状态展示、窄窗口和大节点数量。

## 10. 第三次有界复测：待归类投影与当前文件 UML 修复后

### 10.1 环境与工具

1. 复测 revision 为 `65bb01e16435ffe1d82487d7ab432df8e67bf453`，工作树包含 execution 第 8-10 节所述未提交修复。
2. codebase-memory 项目 `AISc` 可读取 11,514 个节点和 27,069 条边；本次未重建索引。
3. 使用当前新 Codex 任务实际加载的 Project Cognition MCP、工具包自身自动化，以及真实 VS Code Extension Host 交互。
4. 本工具不修改 Unity 运行时、场景或 Prefab，因此继续不选择 Unity MCP、PlayMode、`aisc_debug` 或后端长跑工具。

### 10.2 自动化与 MCP 证据

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| U01 | Server 自动化 | `tools/project_cognition` 执行 `npm test`：15 tests，15 pass，0 fail | 通过 |
| U02 | VS Code adapter 自动化 | `vscode-extension` 执行 `npm test`：4 tests，4 pass，0 fail | 通过 |
| U03 | 新 Codex 任务加载 | 当前任务实际枚举 15 个 Project Cognition MCP 工具 | 通过 |
| U04 | `RELATION_NOT_FOUND` 真实契约 | `expand_relation_evidence("nonexistent:test-relation")` 返回 `ok=false`、`error.code=RELATION_NOT_FOUND` | 通过 |
| U05 | 待归类查询投影 | `get_domain_overview` 返回 `virtual:unclassified`、`proposed` 状态和非持久化 `reference` memberships | 通过 |
| U06 | 当前文件精确图查询 | `WebSocketClient + Assets/Scripts/Core/WebSocketClient.cs` 唯一命中 `Class` | 通过 |

### 10.3 真实 VS Code 宿主证据

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| U07 | Apply 后认知可达 | Project Cognition 功能树显示 `待归类 proposed`，不再为空 | 通过 |
| U08 | 编辑器标题栏入口 | `WebSocketClient.cs` 第 17 行明确声明 `public class WebSocketClient`；点击 `Open Current File UML` 两次均提示 `current file has no class declaration` | 失败 |
| U09 | 待归类 UML 入口 | 从 `待归类` 行内 `Open UML View` 可打开 `UML: 待归类` Webview | 通过 |
| U10 | UML 主视图渲染 | Webview 只有返回按钮；图区域没有类节点、功能域节点或关系，等待 2 秒后仍为空 | 失败 |
| U11 | 关系、证据与源码跳转 | 因 UML 图无节点和边，无法继续展开关系证据或从图跳转源码 | 阻断 |
| U12 | 窄窗口、长名称和 40 节点预算 | 因 UML 图为空，无法执行真实视觉验收 | 阻断 |

### 10.4 第三次复测结论

1. 第二次复测的 Apply 后认知不可达问题已确认修复；`待归类` 同时通过真实 MCP 查询和 VS Code 功能树可达。
2. R11 已确认修复：新 Codex 任务加载的是新 MCP 进程，不存在关系返回稳定 `RELATION_NOT_FOUND`。
3. 阶段 C 仍失败。当前文件首类解析在真实 C# 文件上返回空，违反 execution 第 10 节确认的标题栏入口语义。
4. 即使绕过标题栏、从 `待归类` 直接打开 UML，主图仍为空，违反 plan 15.3.1；关系箭头、证据展开、源码跳转和视觉预算验收因此被阻断。
5. Server 与 adapter 单测全绿但未覆盖上述真实 Extension Host 集成失败。必须回到新的执行会话诊断并修复 U08、U10；本测试会话不修改实现。

## 11. 第四次有界复测：U08 / U10 声明修复后

### 11.1 环境与前置处理

1. 复测前执行 `Developer: Reload Window`，确保 VS Code Extension Host 加载已覆盖安装的新 VSIX；短暂的 data provider 未注册提示在约 3 秒后自行恢复。
2. 当前真实宿主同时报告：Unity 扩展依赖的 Microsoft C# Dev Kit 未安装，Unity 扩展无法激活；未在测试会话中安装或修改开发环境。
3. 继续使用原 `WebSocketClient.cs`、当前 `.project-cognition/AISc.json` 和 `待归类` 入口，不新增 Apply 或修改快照。

### 11.2 自动化与 smoke

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| V01 | Server 自动化 | `tools/project_cognition` 执行 `npm test`：15 tests，15 pass，0 fail | 通过 |
| V02 | VS Code adapter 自动化 | `vscode-extension` 执行 `npm test`：6 tests，6 pass，0 fail；包含扁平 `SymbolInformation` 与嵌套 `DocumentSymbol` | 通过 |
| V03 | 旧快照 Class 投影 smoke | `npm run smoke:uml` 返回 `ok=true`、`memberFiles=3`、`classifiers=4` | 通过 |

### 11.3 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| V04 | U08 当前文件入口 | Extension Host 重载后聚焦 `WebSocketClient.cs`，点击标题栏 `Open Current File UML`，仍提示 `current file has no class declaration` | 失败 |
| V05 | U08 环境依赖 | 同一宿主明确报告 Unity 扩展因缺少 C# Dev Kit 无法激活；当前入口在 document symbol provider 不可用时没有基于已配置 code graph 的降级路径 | 失败 |
| V06 | U10 待归类 Class 投影 | 从 `待归类` 行内入口打开 `UML: 待归类`；等待 2.5 秒后仍只有返回按钮，没有 smoke 声明的 4 个 Class | 失败 |
| V07 | 窄窗口渲染 | 分栏后 UML 可用宽度约 480px，图区域保持空白；无法证明节点无重叠或文本可读 | 阻断 |
| V08 | 关系与证据交互 | 没有类节点或关系边，无法执行证据展开和源码跳转 | 阻断 |

### 11.4 第四次复测结论

1. U08、U10 的声明修复未通过真实宿主复测，阶段 C 继续失败。
2. U08 的新增单测只证明两种 symbol 数据形态的纯函数处理；真实环境中 provider 不可用时，命令仍直接失败。实现需要明确入口是否要求 C# Dev Kit 前置条件，或增加不依赖 IDE language provider 的 code graph 精确查询降级。
3. U10 的正式 stdio smoke 能解析 4 个 Class，但相同快照经 VS Code Webview 打开时没有任何节点，说明 smoke 尚未覆盖 Extension Host 到 Webview 数据投递和渲染链。
4. 必须回到新的执行会话诊断 V04-V06；本测试会话不安装扩展、不修改环境，也不顺手修改实现。

## 12. 第五次有界复测：V04-V06 再次修复后

### 12.1 环境与操作边界

1. 复测前已执行 `Developer: Reload Window`，等待 Project Cognition provider 恢复后继续操作。
2. 当前文件为 `Assets/Scripts/Core/WebSocketClient.cs`，第 17 行明确声明 `public class WebSocketClient : MonoBehaviour`。
3. 真实宿主仍提示 Unity 扩展因缺少 Microsoft C# Dev Kit 无法激活；本测试会话未安装扩展、未修改环境、未执行 Apply。
4. 为排除标题栏图标点击和无障碍元素索引歧义，本轮通过命令面板精确选择 `Project Cognition: Open Current File UML`。

### 12.2 自动化、smoke 与 bundle 门禁

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| W01 | Server 自动化 | `tools/project_cognition` 执行 `npm test`：15 tests，15 pass，0 fail | 通过 |
| W02 | VS Code adapter 自动化 | `vscode-extension` 执行 `npm test`：7 tests，7 pass，0 fail；包含 code graph fallback 选择当前文件最早 Class | 通过 |
| W03 | 旧快照 Class 投影 smoke | `npm run smoke:uml` 返回 `ok=true`、`memberFiles=3`、`classifiers=4` | 通过 |
| W04 | VSIX bundle 门禁 | `npm run verify:bundle` 返回 `ok=true`、655,313 bytes、仅 external `vscode` | 通过 |

### 12.3 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| W05 | code graph fallback | 更新确认框能够识别 `AISc.Assets.Scripts.Core.WebSocketClient.WebSocketClient`，范围为 1 file、1 symbol、1 change，证明当前宿主可从 code graph 定位该 Class；随后取消，未 Apply | 通过 |
| W06 | 当前文件 UML 命令路由 | 命令面板精确选择 `Project Cognition: Open Current File UML` 后，实际打开的标签和面包屑均为 `UML: 待归类`，没有打开 `UML: WebSocketClient` | 失败 |
| W07 | 待归类 UML 数据投递与渲染 | 错误打开的 `UML: 待归类` 已渲染 `GameManager`、`WebSocketClient`、`NpcSpawner` 等 Class 节点，不再是空白 Webview | 通过 |
| W08 | 当前文件 UML 交互验收 | 因入口落入域 UML，无法验证当前文件根节点、一跳关系、证据展开及从当前文件图跳转源码 | 阻断 |
| W09 | tooltip 换行与窄窗口 | 当前文件 UML 未打开，无法对本次声明修复的错误换行门禁及当前文件图窄窗口布局做真实宿主验收 | 阻断 |

### 12.4 第五次复测结论

1. V05 的 code graph 降级能力已在真实宿主得到证实；V06 的域 UML 数据投递和 Webview 渲染也已恢复，真实页面能够显示 Class 节点。
2. V04 仍未通过。精确执行 `Open Current File UML` 却打开 `UML: 待归类`，问题已从“找不到当前文件 Class”收敛为当前文件 UML 命令或其参数到域 UML 的错误路由。
3. 自动化 `7/7` 未覆盖真实 Extension Host 中的命令注册、命令处理器绑定或 Webview 打开参数，因而无法拦截该集成回归。
4. 阶段 C 仍失败；必须回到新的执行会话修复 W06，并增加能区分 `Open Current File UML` 与 `Open UML View` 最终视图目标的集成级门禁。修复后继续在本文件追加有界复测。

## 13. 第六次有界复测：W06 路由修复后

### 13.1 环境与操作

1. 读取 execution 第 13 节后，重新加载真实 VS Code Extension Host；原窗口退出后通过桌面应用入口恢复同一 AISc 工作区。
2. 当前文件仍为 `Assets/Scripts/Core/WebSocketClient.cs`，类声明位于第 17 行；Unity 扩展仍因缺少 C# Dev Kit 无法激活，本会话未安装或修改环境。
3. 继续通过命令面板精确选择 `Project Cognition: Open Current File UML`，排除标题栏图标和无障碍索引歧义。

### 13.2 自动化与 bundle 门禁

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| X01 | Server 自动化 | `tools/project_cognition` 执行 `npm test`：15 tests，15 pass，0 fail | 通过 |
| X02 | VS Code adapter 自动化 | `vscode-extension` 执行 `npm test`：7 tests，7 pass，0 fail | 通过 |
| X03 | current-file bundle 门禁 | `npm run verify:bundle` 返回 `ok=true`、655,332 bytes、仅 external `vscode` | 通过 |

### 13.3 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| X04 | W06 当前文件 UML 路由 | 精确命令打开 `UML: WebSocketClient`；面包屑为 `待归类 / WebSocketClient`，不再错误落入 `UML: 待归类` | 通过 |
| X05 | 当前类首屏 | 图中央渲染单个 `WebSocketClient` Class 节点，所属域继续作为返回导航上下文 | 通过 |
| X06 | 节点源码跳转入口 | 双击 `WebSocketClient` 节点能够切回 `WebSocketClient.cs` | 通过 |
| X07 | 源码定位精度 | 跳转后光标落在第 1 行，而 `WebSocketClient` 类声明位于第 17 行 | 失败 |
| X08 | 一跳关系与证据 | 当前类首屏只有中心节点，没有关系边，无法执行关系选择和证据展开 | 阻断 |
| X09 | tooltip 换行 | 当前图没有关系边，缺少可触发的关系 tooltip，无法完成真实宿主验收 | 阻断 |

### 13.4 第六次复测结论

1. W06 已确认修复：当前文件命令现在以 Class symbol ID 为首屏 focus，同时保留所属功能域面包屑，域 UML 与当前类中心图不再混淆。
2. W08 部分解除：中心节点可以双击返回源码文件，但定位到第 1 行而非第 17 行类声明，源码跳转尚未满足精确符号定位要求。
3. 当前 `WebSocketClient` 中心图没有一跳关系，关系证据、关系 tooltip 和相关窄窗口交互仍无真实数据可验收。
4. 阶段 C 仍未整体通过。必须在新的执行会话修复 X07，并确认当前类中心图缺少关系是数据事实还是关系查询/投影遗漏；修复后继续在本文件追加有界复测。

## 14. 第七次有界复测：X07 / X08 修复后

### 14.1 环境与操作

1. 读取 execution 第 14 节后重载真实 VS Code Extension Host，继续使用 `Assets/Scripts/Core/WebSocketClient.cs` 和当前认知快照。
2. 当前宿主仍缺少 C# Dev Kit；本会话未安装扩展、未修改环境、未执行 Apply。
3. 通过命令面板精确执行 `Project Cognition: Open Current File UML`，并对中心节点、关系线和关系标签执行真实鼠标交互。

### 14.2 自动化、smoke 与 bundle 门禁

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| Y01 | Server 自动化 | `tools/project_cognition` 执行 `npm test`：15 tests，15 pass，0 fail | 通过 |
| Y02 | VS Code adapter 自动化 | `vscode-extension` 执行 `npm test`：7 tests，7 pass，0 fail | 通过 |
| Y03 | UML 集成 smoke | `npm run smoke:uml` 返回 `memberFiles=3`、`classifiers=4`、`classStartLine=17`、`relations=6` | 通过 |
| Y04 | VSIX bundle 门禁 | `npm run verify:bundle` 返回 `ok=true`、656,307 bytes、仅 external `vscode` | 通过 |

### 14.3 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| Y05 | 当前类中心图 | `UML: WebSocketClient` 以中心节点展示当前类，并渲染到 `MessageRouter`、`NpcSocialProtocolController`、`UnitySaveService`、`PauseModel`、`ProtocolClient` 等目标类的调用边 | 通过 |
| Y06 | X07 精确源码定位 | 双击中心节点后打开 `WebSocketClient.cs`，准确选中第 17 至 408 行的完整类范围 | 通过 |
| Y07 | X08 一跳关系投影 | 真实 Webview 显示多条 `calls ...` 有向关系，结果与 smoke 的 `relations=6` 一致 | 通过 |
| Y08 | 临时关系证据展开 | 分别单击、双击关系线及 `calls ...` 标签，均未出现证据面板或方法 qualified-name 证据 | 失败 |
| Y09 | X09 关系 tooltip | 指针停留在关系线和标签超过 1.5 秒，只出现关系高亮，没有可见 tooltip，无法验证多行换行内容 | 失败 |

### 14.4 第七次复测结论

1. X07 已确认修复：Class 的公开 snippet 位置成功补入真实视图，源码跳转不再落到第 1 行。
2. X08 的关系查询和投影部分已确认修复：当前类中心图真实展示 6 条一跳调用关系，不再是单节点空图。
3. X08 的关系证据交互仍未通过；实现声明的“关系点击优先使用当前图临时证据”在真实 Webview 中没有产生可见结果。
4. X09 由“阻断”转为明确失败：关系已经可见，但悬停仅高亮，没有 tooltip。
5. 阶段 C 仍未整体通过。必须进入新的执行会话修复 Y08、Y09，并增加覆盖 Webview 事件绑定及可见证据/tooltip 的宿主级或等价集成门禁；修复后继续在本文件追加有界复测。

## 15. 第八次有界复测：Y08 / Y09 修复后

### 15.1 环境与操作

1. 读取 execution 第 15 节后重载真实 VS Code Extension Host，继续使用 `WebSocketClient.cs` 当前类中心图。
2. 当前宿主仍缺少 C# Dev Kit；本会话未安装扩展、未修改环境、未执行 Apply。
3. 对 `WebSocketClient -> UnitySaveService` 的关系标签/命中区执行真实鼠标点击和悬停，并选择关系证据项验证源码闭环。

### 15.2 自动化与 bundle 门禁

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| Z01 | Server 自动化 | `tools/project_cognition` 执行 `npm test`：15 tests，15 pass，0 fail | 通过 |
| Z02 | VS Code adapter 自动化 | `vscode-extension` 执行 `npm test`：7 tests，7 pass，0 fail | 通过 |
| Z03 | 关系交互 bundle 门禁 | `npm run verify:bundle` 返回 `ok=true`、657,728 bytes、仅 external `vscode` | 通过 |

### 15.3 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| Z04 | Y08 关系命中 | 单击 `calls UnitySaveService` 关系标签/命中区后立即打开 `Relation evidence` 面板 | 通过 |
| Z05 | 临时方法证据 | 面板显示 `CALLS: CloseSocketAsync -> Dispose` 和 `CALLS: ShutdownAsync -> Dispose`，并标明 `Assets/Scripts/Core/WebSocketClient.cs` | 通过 |
| Z06 | 证据源码闭环 | 选择证据项后返回 `WebSocketClient.cs`，选中当前已知类的第 17 至 408 行源码范围 | 通过 |
| Z07 | Y09 tooltip 可见性 | 指针位于关系命中区时显示主题化 tooltip，不再只有线条高亮 | 通过 |
| Z08 | tooltip 内容与换行 | tooltip 分行显示 `calls UnitySaveService`、`call · analyzer · 2 evidence`，无脚本错误、文本截断或错误转义 | 通过 |

### 15.4 第八次复测结论

1. Y08 已确认修复：14px 透明命中区和共享 evidence handler 在真实 Webview 中可用，关系点击能够稳定打开临时方法证据。
2. Y09 已确认修复：自定义 tooltip 可见，摘要、kind、status 和 evidence count 分行清晰显示，先前换行转义问题未复现。
3. 从当前文件入口、类中心图、一跳关系、证据展开到源码返回的主交互链已在真实宿主贯通。
4. 本轮目标全部通过；此前尚未完成的 40 节点预算、长名称和独立窄窗口视觉验收不在本次 Y08/Y09 有界复测范围内，仍需按原 plan 单独完成后才能宣称阶段 C 全面验收通过。

## 16. 第九次有界复测：阶段 C 剩余视觉、容量与可访问性

### 16.1 样本与工具选择

1. 继续使用真实 VS Code Extension Host；通过编辑器分栏把 UML 可用宽度压缩到约 500px，不修改窗口系统设置。
2. 多类与长名称样本选择真实文件 `Assets/Plugins/Sirenix/Odin Inspector/Modules/Unity.Mathematics/MathematicsDrawers.cs`；codebase-memory 返回该文件含 64 个 Class。
3. 源码明确显示第一个 Class 为第 20 行 `MatrixFloat2x2Processor`；`get_code_snippet` 返回 `MatrixBool2x2Processor` 从第 40 行开始。
4. 检查现有 `graph-layout.test.ts` 后确认所谓 bounded layout 用例实际只构造 2 个节点，不能作为 40 节点预算证据。

### 16.2 自动化与 smoke

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| AA01 | Server 自动化 | `tools/project_cognition` 执行 `npm test`：15 tests，15 pass，0 fail | 通过 |
| AA02 | VS Code adapter 自动化 | `vscode-extension` 执行 `npm test`：7 tests，7 pass，0 fail | 通过 |
| AA03 | 现有 UML smoke | `memberFiles=3`、`classifiers=4`、`classStartLine=17`、`relations=6` | 通过 |
| AA04 | 40 节点自动布局门禁 | `graph-layout.test.ts` 仅使用节点 A、B 和一条 edge，没有覆盖 40 节点 | 未覆盖 |

### 16.3 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| AA05 | 约 500px 窄窗口布局 | 中心图保持固定节点尺寸和无重叠布局，使用水平、垂直滚动承载视口外节点，没有动态内容导致的布局跳动 | 通过 |
| AA06 | 窄窗口关系交互 | 窄窗口中 `calls UnitySaveService` tooltip 可读，点击仍可打开两条方法证据；证据面板没有被图节点遮挡 | 通过 |
| AA07 | 窄窗口域视图 | 面包屑返回 `UML: 待归类` 后，4 个 Class 节点纵向排列，无节点互相覆盖 | 通过 |
| AA08 | 面包屑状态一致性 | 从 `WebSocketClient` 中心图返回待归类域后，原 3 个域投影节点与当前临时 Class reference 同时可见 | 通过 |
| AA09 | 多类文件首类确定性 | 对含 64 个 Class 的 `MathematicsDrawers.cs` 执行当前文件 UML，实际打开 `UML: MatrixBool2x2Processor`；源码首类是第 20 行 `MatrixFloat2x2Processor` | 失败 |
| AA10 | 长名称节点基本适配 | 窄窗口中的 `MatrixBool2x2Processor` 节点文本完整位于节点内，没有换行溢出 | 通过 |
| AA11 | 最长名称样本 | 图谱最长 qualified name 为 127 字符，但当前产品没有从任意 symbol 直接打开中心 UML 的测试入口，现有域快照也不包含该节点 | 未覆盖 |
| AA12 | 40 节点真实视图 | 当前域视图为 4 节点、当前类中心图约 7 节点；没有可在不修改快照的前提下触发 40 节点的真实样本 | 未覆盖 |
| AA13 | 关系键盘操作 | 关系 edge 未出现在 VS Code 可访问性树，聚焦 Webview 后 Tab 也未到达关系项，无法使用 Enter/Space 打开证据 | 失败 |

### 16.4 第九次复测结论

1. 窄窗口视觉和交互通过：滚动策略稳定，节点不重叠，tooltip 与证据面板在约 500px 宽度仍可用。
2. 多类文件确定性失败。当前 fallback 显然没有对完整 64 个 Class 进行源码位置排序；现有“earliest class”单测没有覆盖候选数超过位置补齐预算的文件。
3. 键盘关系操作未通过真实可访问性验收；虽然 bundle 含 Enter/Space handler，实际 edge 没有进入可聚焦的可访问性顺序。
4. 40 节点和 127 字符 qualified name 仍不能宣称通过：前者没有对应自动化或真实宿主样本，后者缺少任意 symbol UML 入口和域 membership。
5. 阶段 C 仍未全面通过。必须在新的执行会话修复 AA09、AA13，并补充真实 40 节点布局 fixture/门禁；长 qualified name 应通过可控 fixture 或明确的 symbol UML 测试入口完成验收。

## 17. 用户协助复核：关系证据方法级跳转

### 17.1 复核证据

1. 用户截图：`C:/Users/HP/Pictures/Screenshots/屏幕截图 2026-07-22 145703.png`。
2. `GameManager` 类中心图的 `Relation evidence` 显示 `CALLS: Start -> Load Assets/Scripts/Core/GameManager.cs`；点击蓝色证据项不会跳转到对应方法。
3. codebase-memory 确认 `GameManager.Start` 是独立 Method，qualified name 为 `AISc.Assets.Scripts.Core.GameManager.GameManager.Start`，因此方法级定位事实存在，不应退化为整个 Class。

### 17.2 实现链核对

1. `uml-panel.ts` 构建 evidence QuickPick 时，label 使用方法 qualified name 生成 `Start -> Load`，但导航载荷写为 `symbol: source ?? target`。
2. 对临时 classifier context 关系，`source` / `target` 是 Class `SymbolRecord`，不是证据中的调用方或被调 Method。
3. 选择 QuickPick 后统一执行 `openSymbolLocation(picked.symbol)`，所以实际只会打开或选中类范围，无法定位 label 所承诺的方法。

### 17.3 结论修正

| 编号 | 验证项 | 结果 |
|------|--------|------|
| AB01 | 关系证据面板可见和方法 label 正确 | 通过 |
| AB02 | 点击 `Start -> Load` 跳转对应方法 | 失败 |
| AB03 | 第八次复测 Z06“证据源码闭环” | 撤销；仅证明返回已知类源码，不等于方法级证据跳转 |

1. 用户反馈成立，属于方法级证据导航缺陷。
2. 修复需要让每条临时证据携带可导航的方法 qualified name、文件和精确位置，并明确点击后定位调用方方法还是被调方法；不能继续复用 Class `SymbolRecord` 冒充方法证据。
3. 本测试会话不修改实现；必须进入新的执行会话修复 AB02，并增加 `Start -> Load` 这类方法级 QuickPick 导航回归。

## 18. 第十次有界复测：AB02 方法级证据导航修复后

### 18.1 环境与步骤

1. 读取 execution 第 16 节后启动新的真实 VS Code 进程，确保加载已覆盖安装的 VSIX。
2. 聚焦 `Assets/Scripts/Core/GameManager.cs`，从当前文件入口打开 `UML: GameManager`。
3. 点击 `GameManager -> LocationDatabase` 调用关系，在 `Relation evidence` 中选择 `CALLS: Start -> Load Assets/Scripts/Core/GameManager.cs`。

### 18.2 自动化与 smoke

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| AC01 | VS Code adapter 自动化 | `npm test`：8 tests，8 pass；包含 `method evidence navigates to the source method represented by its label` | 通过 |
| AC02 | Server 自动化 | `npm test`：15 tests，15 pass | 通过 |
| AC03 | UML smoke | `relations=6`、`evidenceMethodStartLine=93`，首条 evidence source 为带位置 Method | 通过 |
| AC04 | VSIX bundle 门禁 | `verify:bundle` 返回 657,938 bytes，仅 external `vscode` | 通过 |

### 18.3 真实 VS Code 宿主

| 编号 | 验证项 | 证据 | 结果 |
|------|--------|------|------|
| AC05 | 方法证据展示 | `Relation evidence` 显示 `CALLS: Start -> Load`，说明路径为 `Assets/Scripts/Core/GameManager.cs` | 通过 |
| AC06 | AB02 调用方方法跳转 | 点击蓝色证据项后切回 `GameManager.cs`，准确选中当前源码第 132 至 149 行的完整 `void Start()` 方法 | 通过 |
| AC07 | 类范围误跳转回归 | 未再选中第 10 行开始的整个 `GameManager` Class | 通过 |

### 18.4 第十次复测结论

1. AB02 已确认修复：evidence label、说明路径和导航对象现在来自同一条方法证据。
2. 当前约定明确落到调用方方法；`Start -> Load` 选择后定位 `GameManager.Start`，行为与 execution 声明一致。
3. 第八次复测 Z06 的错误判定继续保持撤销，但其对应功能现已由 AC06 的方法级真实证据重新验证通过。
4. 本轮目标全部通过；阶段 C 仍受第九次复测 AA09、AA13 和 40 节点未覆盖项约束，不能据此宣称全面通过。
