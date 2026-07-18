# 项目功能索引重构执行记录

> 设计方案: [plan.md](2026-07-14_项目功能索引重构_plan.md)

## 实际改动

1. 将 `docs/AIChanges/` 根目录中的 183 份 plan、execution 和 handoff 迁入按功能划分的目录。
2. 重写 `docs/ProjectIndex.md`、`docs/AIChanges/ChangeIndex.md` 和两级 README，使功能域成为第一导航维度。
3. 为文档目录、Unity 脚本一级模块、后端正式模块、测试脚本和共享配置补充目录说明。
4. 更新 `AGENTS.md`，把 AI 查找顺序改为“功能域 -> 当前口径 -> 代码目录 -> 必要历史证据”。
5. 新增 ADR-0005，并同步更新 ADR 索引、项目治理 Workstream、Roadmap、设计索引和命名规范。
6. 批量替换 Markdown 中指向旧 AIChanges 根层文件的路径。

## 文件组织结果

- 项目治理、记忆、导航、NPC 行为、对话、前端架构、协议联调、测试诊断分别拥有独立证据目录。
- 历史 handoff 已归档到 `Archive/Handoffs/`。
- `docs/AIChanges/` 根目录只保留 README 和功能索引。
- 日期仍保留在执行证据文件名中用于审计，但不再参与目录和索引分类。

## 回写内容

- Workstream: `docs/Workstreams/ProjectGovernance/README.md`
- ADR: `docs/DecisionRecords/ADR-0005-functional-document-index.md`
- 总索引: `docs/ProjectIndex.md`
- 命名规范: `docs/DesignDocs/ProjectNamingAndIndexing.md`

## 遇到的问题

第一次批量替换旧路径时，PowerShell 的排除目录正则书写错误，导致替换步骤未执行。文件迁移已正常完成；随后改用字符串路径判断重新执行，避免依赖易错正则。

## 验证方式

1. 检查 AIChanges 根目录不存在 plan、execution 和 handoff。
2. 检查约定范围内的功能目录均存在 README 或明确主索引。
3. 检查全项目 Markdown 本地链接。
4. 检查 plan / execution 顶部互链。
5. 使用 `rg` 检查是否仍存在指向 AIChanges 根层历史文件的旧路径。

## 验证结果

1. AIChanges 根目录 plan / execution / handoff 数量：0。
2. 指向 AIChanges 根层历史文件的旧路径数量：0。
3. 排除外部 URL、模板占位符和 artifacts 原始产物后，本地 Markdown 失效链接数量：0。
4. 八个功能证据目录均存在 README，记录数量分别为：Dialogue 26、FrontendArchitecture 42、Memory 27、Navigation 23、NpcBehavior 8、ProjectGovernance 29、ProtocolAndIntegration 6、TestingAndDiagnostics 19。
5. 三份历史 plan 原本没有 execution，已明确标记“未创建”，没有伪造执行结果。

## 未完成项

无。
