# ADR-0004: 项目文档治理先做结构索引，暂不补向量库

## 状态

Accepted

## 背景

`docs/AIChanges/` 已经积累大量 plan / execution / handoff。问题表现为：

1. 日期文件过多，难以按系统追踪。
2. 大方向和具体实现之间缺少中间计划层。
3. 旧设计文本、最新 handoff 和执行记录容易漂移。
4. 后续 AI 容易把最近日志当作完整项目事实。

一个可能方案是为项目文档补向量库，让 AI 通过语义检索查历史。但当前主要缺口并不是“搜不到相似文本”，而是“没有稳定结构告诉 AI 哪些文本仍有效”。

## 决定

近期先做结构化治理，不立即补文档向量库：

1. `docs/Roadmap.md` 管长期目标。
2. `docs/Workstreams/*/README.md` 管系统状态。
3. `docs/DecisionRecords/ADR-*.md` 管架构决定。
4. `docs/AIChanges/ChangeIndex.md` 管执行证据索引。
5. `docs/AIChanges/` 继续保存历史计划和执行记录。

## 为什么不立即补向量库

1. 向量库不能判断设计是否已废弃，只能找语义相近文本。
2. 如果没有 Workstream / ADR 元数据，向量命中旧 v0.5 设计反而可能误导实现。
3. 需要额外维护切分、embedding、重建、失效、来源追溯和查询工具。
4. 当前规模下，`rg` + 结构索引已经足够支撑高质量定位。
5. 文档治理先做清楚后，未来再补向量库会更可靠。

## 何时重新评估向量库

满足以下任意两项时，可以重新立项：

1. `docs/AIChanges/` 超过 300 份执行记录，并且人工维护 ChangeIndex 明显吃力。
2. 经常需要用自然语言跨多个系统追问历史原因。
3. 已经稳定要求每份 plan / execution 写入 Workstream、Roadmap item、ADR、Status 元数据。
4. 能接受一个只读离线索引，不参与运行时代码路径。
5. 有脚本可以从 markdown front matter 或固定字段重建索引，避免人工维护向量库。

## 如果未来补向量库

推荐形态：

1. 独立于游戏运行时的开发辅助索引。
2. 只读生成，不手工编辑。
3. embedding 输入包含文档路径、标题、Workstream、ADR、Status、摘要和正文分块。
4. 检索结果必须显示来源路径和状态。
5. 默认不索引 artifacts 原始日志，只索引摘要和 execution。

## 影响

1. 当前治理重点是补结构索引，而不是加数据库。
2. 后续 AI 不应把“没有向量库”当作项目管理瓶颈。
3. 如果未来补向量库，必须以现有 Roadmap / Workstream / ADR 为元数据基础。

## 相关入口

1. `docs/Roadmap.md`
2. `docs/Workstreams/ProjectGovernance/README.md`
3. `docs/AIChanges/ChangeIndex.md`
