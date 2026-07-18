> 设计方案: [2026-07-12_项目运行架构治理_plan.md](2026-07-12_项目运行架构治理_plan.md)

# 项目运行架构治理执行记录

## Workstream

ProjectGovernance

## Roadmap item

GOV

## 相关 ADR

1. `docs/DecisionRecords/ADR-0004-document-governance-and-vector-index.md`
2. `docs/DecisionRecords/ADR-0001-memory-v07-light-graph.md`
3. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`
4. `docs/DecisionRecords/ADR-0003-unity-mcp-asset-first.md`

## 实际改动清单

### 1. 新增路线图层

新增 `docs/Roadmap.md`：

1. 汇总项目当前工作流。
2. 记录当前阶段、近期目标和入口。
3. 固定当前冻结或暂缓事项。
4. 明确非平凡修改应标注 Workstream / Roadmap item / ADR。

### 2. 新增工作流索引层

新增 `docs/Workstreams/`：

1. `docs/Workstreams/README.md`
2. `docs/Workstreams/ProjectGovernance/README.md`
3. `docs/Workstreams/Memory/README.md`
4. `docs/Workstreams/Navigation/README.md`
5. `docs/Workstreams/Dialogue/README.md`
6. `docs/Workstreams/FrontendArchitecture/README.md`

每个系统 README 记录当前目标、工程口径、已完成阶段、下一阶段建议、暂缓事项和相关证据入口。

### 3. 新增 ADR 决策记录层

新增 `docs/DecisionRecords/`：

1. `docs/DecisionRecords/README.md`
2. `docs/DecisionRecords/ADR-0001-memory-v07-light-graph.md`
3. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`
4. `docs/DecisionRecords/ADR-0003-unity-mcp-asset-first.md`
5. `docs/DecisionRecords/ADR-0004-document-governance-and-vector-index.md`

其中 ADR-0004 明确当前不立即为项目文档补向量库，先用结构索引解决有效性和边界问题。

### 4. 新增 AIChanges 变更索引

新增 `docs/AIChanges/ChangeIndex.md`：

1. 按项目治理、记忆、导航、对话、前端职责、资产视觉分组。
2. 将高频历史 plan / execution 汇总为系统入口。
3. 记录维护规则，要求后续非平凡执行记录回填 ChangeIndex。

### 5. 回写现有入口

更新：

1. `AGENTS.md`
   - 新会话启动链改为 ProjectIndex → Roadmap → Workstream → ADR → handoff → ChangeIndex → 执行证据。
   - plan / execution 要求补充 Workstream、Roadmap item、相关 ADR 和索引回写情况。

2. `docs/ProjectIndex.md`
   - 新增 Roadmap、Workstreams、DecisionRecords、ChangeIndex 入口。
   - 新会话推荐阅读顺序改为先建立路线图和工作流上下文。

3. `docs/DesignDocs/Index.md`
   - 修正最新 handoff 指向为 `HANDOFF_2026-07-12.md`。
   - 增加 Roadmap / Workstreams / DecisionRecords 提示。

4. `docs/AIChanges/README.md`
   - 将 AIChanges 定位为证据库。
   - 增加 ChangeIndex 使用与维护规则。

5. `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-12.md`
   - 增加项目运行架构治理状态。
   - 将本轮治理记录加入最近关键执行记录。

6. `docs/DesignDocs/CodebaseBigPicture.md`
   - 前端结构问题阅读链路加入 Roadmap、FrontendArchitecture Workstream。
   - 导航问题阅读链路加入 Navigation Workstream 和 ADR-0002。

## 向量库结论

本轮结论：暂不补项目文档向量库。

原因：

1. 当前痛点是“哪些文本仍有效、属于哪个系统、是否推翻当前口径”，不是单纯语义检索。
2. 向量库容易命中过期设计，例如旧 v0.5 记忆设想，反而加重误导。
3. 如果没有 Workstream / ADR / Status 元数据，向量检索不能替代结构治理。
4. 当前用 `rg`、Roadmap、Workstream、ADR、ChangeIndex 已能覆盖近期协作需要。

后续满足以下条件时再评估：

1. `docs/AIChanges/` 超过约 300 份执行记录。
2. 经常需要自然语言跨系统追问历史原因。
3. plan / execution 已稳定写入 Workstream、Roadmap item、ADR、Status 元数据。
4. 可以接受只读离线索引，不进入游戏运行时链路。

## 遇到的问题

1. 首次回写 `ProjectIndex.md` 的大块补丁因原文空格差异未命中，已改用小补丁分段更新。
2. `DesignDocs/Index.md` 和 `AGENTS.md` 均存在旧的 `HANDOFF_2026-07-11.md` 启动指向，已修正。

## 验证方式

1. 检查 `docs/Workstreams/` 与 `docs/DecisionRecords/` 新文件均已创建。
2. 使用 `rg` 检查启动入口中不再出现过期 `HANDOFF_2026-07-11.md` 指向。
3. 使用 `rg` 检查 `AGENTS.md`、`ProjectIndex.md`、`AIChanges/README.md`、最新 handoff 中已出现 Roadmap / Workstreams / DecisionRecords / ChangeIndex。
4. 使用脚本检查 `ChangeIndex.md` 中的实际 markdown 文件引用；仅模板词 `_plan.md` / `_execution.md` 被识别为非路径占位。

本轮为文档与协作架构治理，不涉及代码编译。

## 未完成项

1. `ChangeIndex.md` 目前是高频系统初始索引，不是全量历史清单。
2. 还没有增加自动校验脚本检查 plan / execution 的 Workstream 标注。
3. 未实现文档向量库；已在 ADR-0004 记录重新评估条件。
