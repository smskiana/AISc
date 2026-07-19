> 设计方案: [2026-07-19_AI测试工具发现与三会话交付流程_plan.md](2026-07-19_AI测试工具发现与三会话交付流程_plan.md)
>
> 测试记录: [2026-07-19_AI测试工具发现与三会话交付流程_test.md](2026-07-19_AI测试工具发现与三会话交付流程_test.md)

# AI 测试工具发现与三会话交付流程执行记录

## 1. 执行状态

实现完成，待独立测试。本记录只确认规则和文档已按 plan 落地并通过实现期最低门禁；同主题 `_test.md` 尚未由第三个独立会话创建，因此不得据此宣称本次治理整体完成。

## 2. 实际改动

1. `AGENTS.md`
   - 新增测试工具发现硬约束，要求先读测试与诊断 Workstream，再只读被选工具的叶子 README。
   - 将证据类型扩展为 plan / execution / test，并规定三类记录互链与主要功能域归档。
   - 将复杂修改改为三个独立会话，区分实现期最低门禁和独立测试验收。
2. `CLAUDE.md`
   - 移除按最新 handoff / execution 导航的旧口径，改为功能索引优先。
   - 同步三会话流程和测试工具分级发现入口，不复制具体工具清单。
3. `docs/ProjectIndex.md`、`docs/Workstreams/README.md`
   - 新增测试与诊断 Workstream 权威入口。
4. `docs/Workstreams/TestingAndDiagnostics/README.md`
   - 新建第二级工具选择表，覆盖 Unity 自动化测试、后端测试、专用跑测脚本、`aisc_debug`、`aisc_control`、Console 和 Unity MCP 资产层检查。
   - 规定测试会话只按风险读取相关叶子入口，并定义 `_test.md` 的证据要求。
5. `Assets/Tests/README.md`
   - 新建 Unity 测试叶子入口，说明 EditMode、PlayMode、白名单 probe 和结构化诊断的边界。
6. `backend/tests/README.md`、`backend/scripts/README.md`、`Assets/Scripts/Diagnostics/README.md`
   - 补充各类工具的选择条件、最小使用规则、产物要求和互相路由。
7. 项目治理与证据索引
   - 更新 `docs/Workstreams/ProjectGovernance/README.md`、`docs/AIChanges/README.md`、`docs/AIChanges/ChangeIndex.md`、`docs/AIChanges/ProjectGovernance/README.md` 和 `docs/AIChanges/TestingAndDiagnostics/README.md`，接纳 test 为正式记录类型。
8. `docs/DesignDocs/ProjectNamingAndIndexing.md`
   - 增加 `_test.md` 命名、三类互链和主要功能域归档规则。

## 3. 与 plan 的差异

1. 未修改 `backend/scripts/check_project_conventions.py`。codebase-memory 可行性检查和源码搜索确认该脚本只校验共享 JSON 业务约定，没有 Markdown 链接或 AIChanges 证据检查 seam；为本轮强行扩展会引入计划外基础设施。
2. 未批量修改历史 plan / execution 和历史跑测记录。新规则只约束新记录，保留历史审计证据原貌。
3. 未修改 Unity 资产、Prefab、场景、SerializeField 或运行时代码，因此 Unity MCP 资产层操作和 `aisc_debug` / `aisc_control` 业务 DTO 同步不适用。

## 4. 实现期最低门禁

1. 使用 codebase-memory 检查现有约定检查器、测试代码和诊断工具分布，确认分级入口可落在既有目录边界。
2. 搜索核心治理文档中的二步流程和“按最新记录”旧口径，并修正本轮直接相关的当前工程入口。
3. 检查新增 Workstream、Unity 测试 README、后端测试/脚本 README 和诊断 README 均存在。
4. `python backend/scripts/check_project_conventions.py` 通过：shared ID、profile 主键和 `location_positions` 一致。
5. 本轮 17 份治理文档的 Markdown 本地链接检查通过；尚未创建的同主题 `_test.md` 作为第三会话占位链接排除。
6. codebase-memory 已以 moderate 模式重建并写入持久化 artifact，结果为 11070 nodes / 25102 edges；当前索引配置排除 `docs/`，状态已回写 `docs/AIChanges/codebase-memory-mcp_更新.md`。

## 5. 文档与索引回写

- `docs/ProjectIndex.md` 已指向测试与诊断 Workstream。
- `docs/Workstreams/README.md` 已登记新 Workstream。
- 项目治理 Workstream 已回写三会话和分级工具发现的当前口径。
- AIChanges 根说明、ChangeIndex 和相关功能目录 README 已接纳 test 记录。
- ADR-0004 / ADR-0005 未被推翻，无需新增 ADR。

## 6. 未完成项

1. 第三个独立测试会话尚未执行。
2. 同主题 `_test.md` 尚未创建；测试会话需要验证规则可发现性、链接完整性、三会话措辞一致性和项目约定检查结果。
