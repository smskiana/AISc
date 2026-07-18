> 设计方案: [2026-07-11_图记忆设计追平_plan.md](2026-07-11_图记忆设计追平_plan.md)

# 图记忆设计追平 — 执行记录

## 完成时间

2026-07-11

## 实际改动清单

### 修改文件

| 文件 | 实际改动 |
|------|------|
| `docs/DesignDocs/MemoryArchitecture.md` | 追加第 32 节“2026-07-11 图记忆实现追平注记”，明确轻量图 + 向量数据层、当前 schema 口径、三种检索模式、Day 0 时间语义、夜间边界、暂缓项和后续优先级 |
| `docs/DesignDocs/memory/graph-memory-model.md` | 在顶部追加第 0 节“当前实现口径 v0.7”，声明旧 v0.5 章节保留为远期设计背景，近期以轻量图联想索引为准 |
| `docs/DesignDocs/Index.md` | 更新 `MemoryArchitecture.md` 与 `graph-memory-model.md` 的说明，最新交接指向 `HANDOFF_2026-07-11.md` |
| `docs/ProjectIndex.md` | 新会话推荐阅读顺序改为 `HANDOFF_2026-07-11.md` |
| `AGENTS.md` | 会话启动必读中的当前 handoff 改为 `HANDOFF_2026-07-11.md`；顶部记忆决策摘要同步为“v0.5 设计 / v0.7 当前口径” |
| `CLAUDE.md` | 同步当前 handoff 指向与记忆决策摘要 |

### 新建文件

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-11_图记忆设计追平_plan.md` | 本轮方案 |
| `docs/AIChanges/Memory/2026-07-11_图记忆设计追平_execution.md` | 本执行记录 |
| `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-11.md` | 最新交接链入口，汇总 7月11日记忆系统状态与后续建议 |

## 关键设计追平内容

### 1. 明确“图”的当前定位

本轮把设计口径从“完整认知图本体”收敛为：

```text
图 = 联想索引层
向量库 = 节点内容 / embedding / importance / 时间 / 归档状态数据层
```

也就是说，图仍然保留，但它不再承担所有记忆内容存储职责。

### 2. 明确当前 schema 与旧 v0.5 schema 的关系

文档现在说明：

1. 当前 `memory_nodes` 是极简节点 ID 表。
2. 当前 `memory_edges` 以双向 `clarity_ab / clarity_ba` 为核心。
3. 节点文本、类型、importance、created_day、archived 存在向量层。
4. 旧 v0.5 中 `energy / precision / original_text / is_core` 等字段是远期理想 schema，不是近期必须追齐项。

### 3. 补齐三种检索模式

文档已写明当前三种模式：

1. `player_dialogue`
2. `npc_dialogue`
3. `nightly_impression`

并说明三者共享多跳图路由流程，但参数和偏好不同。

### 4. 补齐玩家背景与时间语义

文档已明确：

1. 玩家背景是 Day 0 长期记忆。
2. 检索上下文必须带 `[Day 0]` / `[第N天]` 时间标签。
3. Day 0 “听说 / 准备”不是永久当前事实。
4. 后续玩家真实行动应写入 Day N 新记忆，自然更新旧语义。

### 5. 明确暂缓项

文档已把以下旧设计降为远期方向：

1. 全节点 `energy / precision` 生命周期
2. 大规模 `similar_to` 边网络
3. 四阶段完整退化状态机
4. 完整四策略选择器与思考预算
5. 反思独立模块
6. 节点融合作为核心演化机制

## 验证方式

### 1. 交接链指向检查

执行：

```powershell
rg -n "HANDOFF_2026-07-10|HANDOFF_2026-07-11" AGENTS.md CLAUDE.md docs/ProjectIndex.md docs/DesignDocs/Index.md docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-11.md
```

结果：

1. 新入口均指向 `HANDOFF_2026-07-11.md`。
2. 上述关键入口中没有残留 `HANDOFF_2026-07-10.md`。

### 2. 文档修改范围检查

本轮只修改文档，没有改后端代码和 Unity 资产。

## 未完成项

1. 没有整理旧 v0.5 长文中的每一处过时 schema，只通过第 32 节和图模型第 0 节声明当前口径优先。
2. 没有更新 `docs/DesignDocs/HANDOFF.md`，该文件继续作为早期设计交接保留。
3. 没有修改代码中的融合实现；文档只标记“融合不应作为当前核心依赖，除非补边继承 / 重连规则”。

## 结论

设计文档已经按 2026-07-11 执行记录追平。

后续讨论“图有没有必要”或继续开发记忆系统时，应以：

1. `MemoryArchitecture.md` 第 32 节
2. `graph-memory-model.md` 第 0 节
3. `HANDOFF_2026-07-11.md`

作为当前依据，而不是直接按旧 v0.5 全概念图推进。
