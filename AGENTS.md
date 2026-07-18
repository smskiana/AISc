## 项目内容定位与上下文读取（功能优先、少读优先）

项目内容只按功能域定位；日期仅用于审计，不得按最新 handoff、execution 或会话顺序导航。总入口是 `docs/ProjectIndex.md`，受维护目录由自身 `README.md` 说明功能、内容和进一步入口。

默认按以下最小链路读取，并仅在必要时扩展：

1. 读取本文件，从 `docs/ProjectIndex.md` 选择功能域；索引只用于定位，不等于全文必读。
2. 读取 1 个对应的 `docs/Workstreams/<功能域>/README.md` 和目标代码目录的 `README.md` / `Index.md`，再用 `rg` 搜索具体符号、配置键和调用链。
3. 仅当任务涉及路线图排期、系统边界或跨系统影响时读取 `docs/Roadmap.md`。
4. 仅当准备改变系统口径、推翻既有边界、引入新基础设施，或 Workstream 明确引用时读取相关 ADR 正文；平常只查 ADR 索引。
5. 仅当需要追溯实现原因时，从 `docs/AIChanges/ChangeIndex.md` 进入功能目录，按主题读取最相关的 1-3 份 plan / execution；不得按日期筛选“最近记录”。
6. `docs/AIChanges/Archive/Handoffs/` 只作归档；仅在用户明确要求接续指定会话，或功能索引和代码均无法说明遗留状态时读取指定 handoff。
7. `docs/DesignDocs/` 下旧文档默认只承担设计说明和追溯作用；仅在任务直接涉及对应设计、Workstream / ADR 明确要求或代码语义无法判断时，按 `docs/DesignDocs/README.md` 和 `Index.md` 的功能分类读取相关章节。
8. 代码阅读从最小入口逐步扩展；仅在测试失败、类型依赖不明或跨模块契约不清时扩大范围，禁止因“大范围改动”或“保险”而预读大量无关代码和旧文档。
9. 若目录 README、Workstream 或功能索引明显过期，只修正本轮直接相关的功能入口；不得新增日期索引、最新记录列表或 handoff 补丁维持导航。
10. 如果需要追溯代码的复杂调用链可以使用codebase-memory-mcp工具进行追溯，每次重大更新记得更新项目codebase-memory-mcp的向量库。（注意同步向量库的最后更新时间`docs/AIChanges/codebase-memory-mcp_更新.md`）

---

# AI 开发规则

## 1. 核心行为底线（必须遵守）

1. **变更策略**：修 bug、补小功能和局部修正时强制最小修改，只改明确范围；新系统设计、结构治理和用户已明确同意的大改，不得为了“少改”继续沿用失衡结构。
2. **协作编辑**：编辑前读取最新内容，尊重人工修改；有冲突先询问，并优先复用现有符号、函数和结构。
3. **类减重与扩展性（硬约束）**：类已明显过重，或本轮会继续塞入多职责、多状态、多分支、多依赖时，必须先向用户请求“减重”指令，禁止“先凑合，后面再拆”。无论是否触发减重，都必须预留职责边界、扩展位或可替换接口。
4. **Unity MCP 优先（硬约束）**：场景、Prefab、SerializeField 连线、UI 结构、控件摆放、编辑器生成流程等资产层问题，必须先用 Unity MCP 在编辑器资产层解决，不得用运行时代码兜底。Unity MCP 不可用时立即停止任何修改并请求用户指示；执行前必须阅读 [UnityMCPUsageRules.md](/F:/GameProject/unity/AISc/docs/DesignDocs/UnityMCPUsageRules.md:1)。
5. **命名与索引规范**：项目命名和文件索引统一遵循 [ProjectNamingAndIndexing.md](/F:/GameProject/unity/AISc/docs/DesignDocs/ProjectNamingAndIndexing.md:1)；Unity 场景、Prefab、UI 层级标签同时参考 `docs/DesignDocs/UnityNamingTags.md`。
6. **交付要求**：始终使用中文；复杂需求先出方案，通过后再实现；完成后输出修改点清单，代码片段必须标注源文件行号。
7. **抽象能力**：处理 3 种及以上或未来可能增加的 case 时，必须考虑能否统一抽象（如资源占用），不得滥用 switch-case 和 if-else。
8. **文档污染防范**：功能修改后必须检查相关文档是否仍与实际功能一致；不一致时立即修正。
9. **AI 诊断钩子同步（硬约束）**：
   - 调试 Unity 运行时功能时，优先用项目专用诊断钩子 `aisc_debug` 读取结构化状态，再结合 Console、测试和其他 Unity MCP 工具；已有结构化钩子可用时，不得只凭零散日志猜测，必要时也可以使用编辑器专有控制钩子`aisc_control`控制游戏运行。
   - 新增或修改功能时，必须检查关键状态、执行阶段、失败原因和关联 ID 是否已被对应诊断 DTO、provider 或 MCP action 覆盖；业务语义变化时，同步修改诊断钩子和控制钩子、相关测试和入口文档。
   - 如果有测试需求应该优先考虑按照要求新增可复用的`aisc_debug`和`aisc_control`的功能，但必须同步文档。
   - 功能本体、诊断钩子、控制钩子和验证未同步完成前，不得宣称任务完成；确实不适用时，必须在 execution 中明确原因。

## 2. 代码注释

1. 绝不修改或删除原有注释。
2. AI 新增或实质性修改的函数，定义前至少有一行功能注释（C# `///` 或 `//`，Python `"""` 或 `#`）。
3. 复杂分支补简短行内注释，但禁止冗长复述代码。
4. 不得只为补注释修改未改动的旧函数；确有需要时仅补函数头注释。

## 3. 实际修改的 plan / execution（互相索引）

只有已确认将进入实际实现的修改才需要在 `docs/AIChanges/<主要功能域>/` 记录 plan（执行案） / execution（执行记录）。实际实现修改包括代码、配置、数据库 schema、Unity 场景 / Prefab / 资产连线、共享 JSON、正式设计口径、可运行脚本、测试及影响运行行为的文档规范变更。

纯探索、读代码、讨论、未确认实施的方案草案、排期、优先级、任务拆分和仅记录未来事项不创建 plan / execution；需落文档时直接更新 Roadmap、Workstream 或设计文档，用户未要求落文档则不写文件。

触发规则：

1. 已确认实施且预计新建文件 >=2 个或修改文件 >=3 个：修改前创建唯一的 `YYYY-MM-DD_<主题>_plan.md`，完成后创建对应 `_execution.md`。
2. 单文件几行的小修：可跳过 plan，但完成后必须创建 execution。
3. plan 记录需求理解、Workstream / Roadmap item、相关 ADR、方案、涉及文件和风险；execution 记录实际改动、索引 / Workstream / ADR 回写、问题、验证和未完成项。
4. plan 顶部写 `> 执行记录: [execution.md](YYYY-MM-DD_<主题>_execution.md)`；execution 顶部写 `> 设计方案: [plan.md](YYYY-MM-DD_<主题>_plan.md)`。未创建 plan 时，execution 必须明确说明。
5. 禁止在 `docs/AIChanges/` 根目录创建 plan、execution 或 handoff。

### 方案与执行会话分离（硬约束）

1. 复杂实现的方案与执行默认放在两个独立对话。若任务已确认实施且预计触发 plan 阈值，方案对话必须完成分析、边界、步骤、风险和验收标准，并直接创建唯一的 `_plan.md`；随后要求用户在新对话中引用该 plan 执行，不得因“顺手”、上下文已读完或用户未主动切换而继续实现。
2. 用户明确坚持同一对话执行时，必须先评估上下文负载；仅当上下文较少、目标边界清晰且相关文件和约束仍可可靠追踪时，才可例外继续。
3. 执行对话必须以该 `_plan.md` 为唯一方案来源，不得重新制定或创建第二份 plan；仅当原方案无法执行、实现边界发生变化或用户要求调整时，停止执行并在独立方案对话中更新原 plan。
4. 已包含大量代码、日志、历史文档、多轮诊断、跨系统讨论或长方案时，必须拒绝同对话执行并要求新建对话，不得以压缩总结规避；单文件小修、机械修改和无需复杂方案的任务不受此限制。

开始任何修改前，必须先用 `rg` 或索引轻量检查 `docs/Workstreams/`、`docs/DecisionRecords/` 和 `docs/AIChanges/ChangeIndex.md` 的相关口径，只读取命中条目，不做全量历史阅读。

## 4. 低级错误预防

遇到可复用且已更正的错误后：

1. 分析错误现象、根本原因和正确做法。
2. 创建独立明细文件并回写错误索引。
3. 后续修改前先回顾错误索引，不在本文件堆积细节。

错误索引入口：[ErrorPreventionIndex.md](/F:/GameProject/unity/AISc/docs/DesignDocs/ErrorPreventionIndex.md:1)。
