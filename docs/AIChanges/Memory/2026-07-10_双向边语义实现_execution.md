> 设计方案: [2026-07-10_双向边语义实现_plan.md](2026-07-10_双向边语义实现_plan.md)

# 双向边语义实现 — 执行记录

## 完成时间
2026-07-10

## 本次完成内容

本轮已按“方案 B：显式维护双向边语义”完成后端实现，不再只是书面预研。

核心变化有三部分：

1. 抽出共享边语义规则，统一生成 `clarity_ab / clarity_ba`
2. 初始化图和午夜入图改为复用这套规则
3. 图检索改为按“当前起点实际方向”的 clarity 取邻边

## 实际改动清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `backend/src/memory/edge_semantics.py` | 统一维护各类边的双向 clarity 规则 |
| `docs/AIChanges/Memory/2026-07-10_双向边语义实现_plan.md` | 本轮实施计划 |
| `docs/AIChanges/Memory/2026-07-10_双向边语义实现_execution.md` | 本执行记录 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/src/database/sqlite_client.py` | 新增 `get_directional_neighbors()`，按起点方向返回 `neighbor_id / direction / directional_clarity` |
| `backend/src/memory/retrieval.py` | `_graph_recall()` 改用方向感知邻边，不再取 `max(clarity_ab, clarity_ba)` |
| `backend/src/memory/manager.py` | 午夜提取入图时按边类型和节点类型显式生成双向 clarity，并补了已有节点类型读取 |
| `backend/src/npc/state_manager.py` | 初始 `relationship / involved / felt` 边改为统一走共享边语义规则 |

## 关键实现说明

### 1. 建边不再是一刀切 `importance / importance*0.7`

现在会按边类型显式区分，例如：

1. `relationship`：双向都强，但反向略低
2. `involved`：`event -> person/self` 更强，`person/self -> event` 也维持可召回
3. `located_at` / `happened_at`：事件指向地点/时间更强，反向保留中低强度
4. `felt`：双向都较强，方便情绪回忆

### 2. 检索开始真正使用方向语义

现在从起点节点检索时，会按：

1. 当前边是 `ab` 还是 `ba`
2. 当前方向对应的 `directional_clarity`

来排序，而不是把两侧清晰度混成一个分数。

### 3. 初始图和后续入图口径统一

这轮把 `state_manager` 与 `memory.manager` 的建边规则统一到了同一个模块，避免后面继续出现：

1. 初始图一套权重
2. 午夜提取另一套权重
3. 检索层再自己解释一套

## 验证方式

### 1. 语法检查

执行：

```powershell
python -m py_compile backend/src/memory/edge_semantics.py backend/src/database/sqlite_client.py backend/src/memory/retrieval.py backend/src/memory/manager.py backend/src/npc/state_manager.py
```

结果：通过。

### 2. 导入检查

执行：

```powershell
python -c "import os, sys; os.chdir('backend'); sys.path.insert(0, os.getcwd()); import src.main; print('import ok')"
```

结果：输出 `import ok`。

### 3. 定向双向语义 smoke

在临时 SQLite 中写入一条 `event -> person` 的 `involved` 边，然后分别从事件节点和人物节点做图召回。

结果：

1. `event -> person` 方向 clarity 为 `0.9`
2. `person -> event` 方向 clarity 为 `0.756`
3. 从 `person` 起点检索时，能够正确召回 `event`
4. 返回结果里方向标记为 `ba`，说明检索侧已经按真实方向解释边

### 4. 冷启动 smoke

在临时数据库执行 `StateManager.cold_start()`。

结果：

1. `memory_nodes = 49`
2. `memory_edges = 44`
3. `npc_impressions = 25`

说明初始化链路在新规则下可正常完成。

## 本轮未做

本轮刻意没有继续展开更大的图重构，以保持目标收敛：

1. 融合节点继承旧边
2. 节点唯一约束和复用深改
3. `recover_clarity()` 的完整闭环接入
4. 新事件与旧事件的自动补边体系

## 当前结论

这轮改完后，图的“边方向”不再只是存储层字段，而是开始真正参与：

1. 初始图构建
2. 午夜入图
3. 图检索

下一步如果继续做图连接完善，最值得接的是：

1. 人物/地点锚点复用代码化
2. 新事件对旧事件的规则补边
3. 融合节点继承旧边
