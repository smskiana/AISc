> 设计方案: [2026-07-11_节点融合边继承_plan.md](2026-07-11_节点融合边继承_plan.md)

# 节点融合边继承 — 执行记录

## 完成时间

2026-07-11

## 本次目标

补完节点融合当前最大的缺口：融合节点不能只是“新建向量 + 归档旧节点”，还必须继承旧图邻域，否则会变成孤点，检索路径也会断。

## 实际改动

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/src/memory/evolution.py` | 融合前构建继承边；融合后插入继承边、删除旧边、删除旧图节点、归档旧向量节点；补可达性日志 |
| `backend/src/database/sqlite_client.py` | 新增 `get_edges_touching_node_ids()` 与 `delete_edges_touching_node_ids()` |
| `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-11.md` | 将“融合未补边继承”更新为“基础闭环已补，但仍不是完整退化主机制” |
| `docs/DesignDocs/MemoryArchitecture.md` | 更新第 32 节当前口径与后续优先级 |
| `docs/DesignDocs/memory/graph-memory-model.md` | 更新当前实现口径表述 |

### 新建文档

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-11_节点融合边继承_plan.md` | 本方案 |
| `docs/AIChanges/Memory/2026-07-11_节点融合边继承_execution.md` | 本执行记录 |

## 关键实现

### 1. 融合节点继承旧邻边

融合 `A + B -> M` 时，会先收集所有连接到 A 或 B 的边。

处理规则：

1. A-B 内部边跳过，不继承。
2. 外部邻边会转为 M 与原 neighbor 的边。
3. 相同 `neighbor + edge_type` 的继承边合并。
4. clarity 双向分别取最大值。
5. target_importance 取最大值。

### 2. 保留方向语义

旧边方向会被显式换算：

```text
A -> neighbor 变成 M -> neighbor
neighbor -> A 变成 neighbor -> M
```

不会简单复制 `clarity_ab / clarity_ba`，避免方向反转。

### 3. 旧节点退场

继承边插入后：

1. 删除 A / B 相关旧边。
2. 删除 A / B 的 SQLite `memory_nodes`。
3. 将 A / B 在向量层标记为 `archived=1`。

这样日常图路由不再走旧节点，但强制回忆仍可在向量层 include archived 时追溯旧文本。

### 4. 防孤点

如果 A / B 没有任何可继承外部邻边，本轮会跳过融合，不会创建孤立融合节点。

## 验证

### 1. Python 编译

执行：

```powershell
python -m py_compile backend/src/memory/evolution.py backend/src/database/sqlite_client.py
```

结果：通过。

### 2. 临时库融合 smoke

使用临时 SQLite + 假向量存储 + 假 LLM 跑了一次 `A + B -> M`。

验证点：

1. 旧图节点 A / B 被删除。
2. 旧向量节点 A / B 被标记 archived。
3. 融合节点 M 创建成功。
4. M 继承 self / location 外部邻边。
5. A/B 内部 `similar_to` 边未继承。
6. `created_day=0` 来源节点没有被 `or 默认值` 覆盖；融合节点日期取来源中较新的 Day 2。
7. 方向 clarity 正确：
   - `A/B -> self` 合并为 `M -> self`
   - `self -> A/B` 合并为 `self -> M`
   - `location -> A` 正确换算为 `location -> M`

smoke 关键输出：

```text
nodes: node_test_loc, node_test_merged_xxx, node_test_self
edges:
- node_test_merged_xxx -> node_test_self involved clarity_ab=0.4 clarity_ba=0.9
- node_test_merged_xxx -> node_test_loc located_at clarity_ab=0.3 clarity_ba=0.7
created_day: 2
```

### 3. 文档旧口径检查

执行 `rg` 检查：

```powershell
rg -n "节点融合仍不是稳定主机制|旧边继承 / 重连规则还不完整|必须补旧边继承|需先补边继承" docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-11.md docs/DesignDocs/MemoryArchitecture.md docs/DesignDocs/memory/graph-memory-model.md
```

结果：无匹配。

## 未完成项

1. 当前只补“基础边继承闭环”，不实现旧 v0.5 的完整四阶段退化状态机。
2. 当前没有新增 `memory_merge_sources` 来源追溯表；旧来源只能通过 archived 向量节点保留。
3. 当前没有做长测统计“融合节点后续实际被检索命中次数”，后续如果要把融合作为更强机制，应补可达性指标。
4. 当前仍只做 event 节点两两融合，不做多节点聚类融合。

## 结论

节点融合现在不再是“只创建新节点但断图”的半成品。

当前机制已经形成基础闭环：

```text
相似事件 A/B
→ LLM 概括为融合节点 M
→ M 继承 A/B 外部邻边
→ A/B 从图层退场
→ A/B 向量层 archived 保留来源文本
```

但项目当前主遗忘机制仍是：

```text
边 clarity 衰减 + 孤点 archived 归档
```

融合已经可用，但还不建议继续扩成完整认知图本体。
