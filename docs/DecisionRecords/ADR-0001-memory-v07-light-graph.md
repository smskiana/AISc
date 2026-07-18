# ADR-0001: 记忆系统采用 v0.7 轻量图 + 向量数据层

## 状态

Accepted

## 背景

早期 v0.5 设计包含较完整的联想记忆图、四阶段退化、全图 `similar_to` 等远期设想。实际实现推进后，系统已经收敛为更轻量的工程口径：图层负责联想路径，向量层负责语义内容和兜底。

如果后续继续按旧 v0.5 文本追齐，会扩大复杂度，并反复重构已经跑通的 v0.7 链路。

## 决定

近期记忆系统采用 v0.7 口径：

1. 每个 NPC 独立维护轻量联想图。
2. SQLite 图层保存节点 ID、边、边类型和双向 clarity。
3. LanceDB / SQLite 向量层保存节点内容、embedding、importance、created_day、archived。
4. 白天检索按模式控制深浅，夜间印象做更宽检索。
5. 当前遗忘机制以边 clarity 衰减 + archived 归档为主。

## 放弃或暂缓

1. 完整四阶段退化。
2. 全图 `similar_to` 建边。
3. 节点 energy / precision 等完整认知本体。
4. 围绕旧 v0.5 章节做追齐式开发。

## 影响

1. 新记忆功能应优先提升诊断、可信度、玩家事件接入和长测质量。
2. 旧设计文档中的远期概念只能作为背景，不能自动变成近期 TODO。
3. 若要重新扩张图模型，必须先写新的 ADR。

## 相关入口

1. `docs/Workstreams/Memory/README.md`
2. `docs/DesignDocs/MemoryArchitecture.md`
3. `docs/DesignDocs/memory/graph-memory-model.md`
