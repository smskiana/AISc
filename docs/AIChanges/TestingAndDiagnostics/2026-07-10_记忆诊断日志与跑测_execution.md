> 设计方案: [2026-07-10_记忆诊断日志与跑测_plan.md](2026-07-10_记忆诊断日志与跑测_plan.md)

# 记忆诊断日志与跑测 — 执行记录

## 完成时间
2026-07-10

## 本次完成内容

本轮没有再改记忆语义规则本身，而是补了一轮“可观测性”，并做了定向跑测来验证双向边语义是否真的生效。

本次落地了两件事：

1. 给初始图、午夜入图、图召回补充可开关的诊断日志
2. 跑了一次临时库 smoke test，验证“熟人人物节点是否能回忆到新事件”

## 实际改动文件

### 代码文件

| 文件 | 改动 |
|------|------|
| `backend/src/npc/state_manager.py` | 新增初始图诊断日志，输出每个 NPC 的人物节点数、核心事件数、初始边数 |
| `backend/src/memory/manager.py` | 新增提取前后诊断日志，输出原始节点/边数量、节点类型分布、实际写入边样本 |
| `backend/src/memory/retrieval.py` | 新增检索诊断日志，输出起点节点、邻边摘要、图召回候选、合并排序、最终上下文预览 |

### 文档文件

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/TestingAndDiagnostics/2026-07-10_记忆诊断日志与跑测_plan.md` | 本轮实施计划 |
| `docs/AIChanges/TestingAndDiagnostics/2026-07-10_记忆诊断日志与跑测_execution.md` | 本执行记录 |

## 日志设计说明

### 1. 使用环境变量开关控制

新增日志统一受以下环境变量控制：

```powershell
SAKURA_MEMORY_TRACE=1
```

不开启时，不会额外输出这批诊断日志。

### 2. 初始图日志

会输出类似：

1. `npc=sakura`
2. `person_nodes=5`
3. `core_events=3`
4. `init_edges=10`

用来确认冷启动时基础图规模是否符合预期。

### 3. 入图日志

会输出：

1. 原始提取 `raw_nodes / raw_edges`
2. `node_types`
3. 最多 8 条边样本

每条样本边包含：

1. `type`
2. `from_type`
3. `to_type`
4. `clarity_ab`
5. `clarity_ba`

这能直接看出“双向边语义”是不是按预期写入了。

### 4. 检索日志

会输出：

1. 检索起点节点
2. 每个起点的邻边摘要
3. 图召回候选
4. 合并排序后的 node_id
5. 最终自然语言上下文预览

这能直接检查“人物节点是否真的能回忆到事件节点”。

## 验证方式

### 1. Python 编译检查

执行：

```powershell
python -m py_compile backend/src/memory/retrieval.py backend/src/memory/manager.py backend/src/npc/state_manager.py
```

结果：通过。

### 2. 定向 smoke test

执行方式：

1. 新建临时 SQLite
2. 启用 `SAKURA_MEMORY_TRACE=1`
3. 执行 `StateManager.cold_start()`
4. 构造 Dummy LLM，模拟“鹿岛樱晚上和千早一起试做新口味面包”的一次事件提取
5. 显式复用 `sakura -> 千早` 的已有 `person` 节点
6. 调用 `MemoryManager.extract_and_ingest()`
7. 调用 `RetrievalEngine.retrieve('sakura', 'chihaya', ...)`

### 3. 跑测结果

核心结果：

1. `written = 2`
   - 说明这次模拟提取成功写入了 2 个节点

2. 检索结果中包含：
   - `我晚上和千早一起试做了新口味面包，聊得很开心。`

3. 检索日志显示：
   - 从 `chihaya` 的人物节点出发，能通过 `involved` 的 `ba` 方向回到新事件
   - 对应 clarity 为 `0.756`

4. 入图日志显示：
   - `event -> person` 的 `involved` 边写入为 `clarity_ab = 0.9`
   - `person -> event` 的回忆方向为 `clarity_ba = 0.756`

这说明：

1. 双向边方向语义已经真正落库
2. 人物起点回忆事件的链路已经打通

## 观察到的新现象

虽然新事件已经能被回忆到，但这次检索结果里，排在它前面的还有旧核心事件，例如：

1. `父母车祸去世`
2. `玩家小时候在门口放过牵牛花`

这说明当前状态是：

1. “能不能回忆到”这个问题已经明显改善
2. “是不是优先回忆到最贴近该熟人的事件”还没有完全解决

也就是说，当前瓶颈已经从“方向不可达”转移成了“候选排序还偏粗”。

## 当前结论

这轮日志和跑测证明了两点：

1. 双向边语义不是只停留在字段层，检索时已经真正生效
2. 熟人人物节点现在可以通过反向 clarity 回忆到相关事件

同时也暴露出下一步最值得做的方向：

1. 在图召回排序里增加“与目标人物直接相关”的加权
2. 减少无关高重要旧事件在熟人检索中的抢位
