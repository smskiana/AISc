# Assets 目录总索引补齐方案

> 执行记录: [2026-07-17_assets_directory_index_execution.md](2026-07-17_assets_directory_index_execution.md)

## 需求理解

为 `Assets/` 补充稳定的目录级 README，使后续会话能够先从 Unity 资产总入口判断资源类型，再进入脚本或具体资产目录；不为 Unity 生成目录、第三方包和纯素材叶子目录机械添加 README。

## 所属功能域

- Workstream：`docs/Workstreams/ProjectGovernance/README.md`
- 主要功能域：项目治理
- 相关规范：`docs/DesignDocs/ProjectNamingAndIndexing.md`
- 相关 ADR：`docs/DecisionRecords/ADR-0005-functional-document-index.md`

## 当前问题

1. `docs/ProjectIndex.md` 将 `Assets/` 的入口直接指向 `Assets/Scripts/README.md`，无法覆盖场景、Prefab、数据、字体、材质、Shader、测试等非脚本资产。
2. `Assets/` 根目录缺少自身 `README.md`，不符合受维护功能目录应提供目录说明的现行口径。
3. `Assets/Scripts/` 已有 README 及细分功能入口，不需要复制其详细脚本索引。

## 实施方案

1. 新增 `Assets/README.md`：
   - 说明该目录承载 Unity 客户端代码与游戏资产。
   - 按功能概括一层子目录，区分自维护代码/资产、测试、第三方或 Unity 管理内容。
   - 将 `Assets/Scripts/README.md` 作为代码入口，并提示具体业务应继续按脚本功能 README 或 `rg` 定位。
   - 明确不把普通素材叶子文件逐项登记到总索引。
2. 修改 `docs/ProjectIndex.md`：
   - 将 `Assets/` 的主入口改为 `Assets/README.md`。
   - 保留现有各功能域的具体脚本入口，避免降低定位精度。
3. 完成后新增同主题 execution：
   - 记录实际修改、验证结果、文档同步情况和未完成项。
   - 明确本轮不改变运行时功能，`aisc_debug` / `aisc_control` 同步不适用。
4. 如 Unity 编辑器为新增 Markdown 生成 `.meta`，保留正常生成结果；本轮不修改场景、Prefab、SerializeField 或其他资产连线。

## 涉及文件

- 新增：`Assets/README.md`
- 修改：`docs/ProjectIndex.md`
- 新增：`docs/AIChanges/ProjectGovernance/2026-07-17_assets_directory_index_execution.md`
- 可能由 Unity 生成：`Assets/README.md.meta`

## 风险与控制

1. **索引过细导致维护负担**：只登记一层功能目录和稳定入口，不罗列普通叶子资产。
2. **误把第三方目录纳入自维护范围**：对 `Plugins/`、`TextMesh Pro/` 只说明性质，不要求其内部补 README。
3. **内容快速过期**：目录说明只描述职责，不维护文件数量、最近变更或日期列表。
4. **Unity 资产数据库副作用**：不操作场景和 Prefab；仅确认 Markdown 及其正常 `.meta` 状态。

## 验收标准

1. `Assets/README.md` 可从资产根目录将读者路由到脚本、场景、Prefab、数据、视觉资产、测试及第三方内容。
2. `docs/ProjectIndex.md` 中 `Assets/` 的入口指向 `Assets/README.md`。
3. README 不机械展开纯素材叶子文件，不复制 `Assets/Scripts/README.md` 的详细内容。
4. 新增和修改的 Markdown 本地链接均可解析。
5. execution 与本 plan 互相索引，并明确诊断钩子不适用原因。

## 执行边界

本方案只补齐目录索引，不重命名资产、不调整目录结构、不修改运行时代码，也不处理既有素材命名债。执行会话必须以本文件为唯一方案来源。
