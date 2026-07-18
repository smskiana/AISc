> 设计方案: [2026-07-11_夜间印象多跳图路由_plan.md](2026-07-11_夜间印象多跳图路由_plan.md)

# 夜间印象多跳图路由 — 执行记录

## 完成时间

2026-07-11

## 实际改动清单

### 修改文件 (3)

| 文件 | 实际改动 |
|------|------|
| `backend/src/memory/retrieval.py` | 新增 `nightly_impression` 检索模式；参数比白天更宽；路由提示增加夜间整理偏好；夜间模式对 reflection / emotion 轻微加权 |
| `backend/src/npc/state_manager.py` | 新增 `set_retrieval()`；夜间 `_graph_target_memories()` 优先调用多跳图路由；旧目标名向量搜索保留为兜底；图记忆读取移动到印象并发任务内部 |
| `backend/src/application/runtime.py` | 启动和读档刷新时将 `retrieval` 注入 `state_mgr`，让夜间状态层能复用同一套图路由器 |

### 新建文档 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-11_夜间印象多跳图路由_plan.md` | 本次方案 |
| `docs/AIChanges/Memory/2026-07-11_夜间印象多跳图路由_execution.md` | 本执行记录 |

## 参数落地

新增模式：

```python
"nightly_impression": {
    "max_edges_per_hop": 8,
    "edges_per_route": 3,
    "max_hops": 2,
    "short_term_limit": 6,
    "short_term_days": 7,
    "min_graph_nodes": 4,
    "vector_fallback_limit": 3,
    "vector_search_top_k": 8,
    "final_memory_limit": 6,
}
```

这套参数比白天对话更宽，但仍控制在 2 跳，避免午夜阶段的 LLM 路由数量过快膨胀。

## 关键实现说明

### 1. 夜间不再只靠目标名向量 top_k

`StateManager._graph_target_memories()` 现在优先调用：

```python
retrieval.retrieve(..., mode="nightly_impression")
```

只有在检索器不可用或多跳路由失败时，才回退旧的 LanceDB 目标名向量搜索。

### 2. 没有把夜间图路由提前串行化

原本 `_rebuild_impressions_for_npc()` 在构建 tasks 时就会读取 `graph_memories`。

本次改为：

1. 构建任务时只收集短期记忆、目标信息、旧印象和 fallback 查询向量
2. `_run_impression_task()` 在线程池内部读取 `graph_memories`
3. 同一个任务内继续生成基准印象

这样夜间图路由和印象 LLM 仍然共享现有并发池。

### 3. 运行时注入已补齐

`runtime.start()` 和 `_refresh_vector_services()` 都会调用：

```python
state_mgr.set_retrieval(retrieval)
```

因此新启动和读档后都能保持夜间多跳路由可用。

## 验证结果

### 已完成

1. Python 编译检查通过：
   - `backend/src/memory/retrieval.py`
   - `backend/src/npc/state_manager.py`
   - `backend/src/application/runtime.py`
2. 未重置数据库，直接用当前库执行夜间图记忆 smoke test
3. 当前 `memory_nodes = 69`

### Smoke Test

直接调用：

```python
state._graph_target_memories("kujo", "player", game_day=1)
```

返回：

```text
- 记得: 小李准备重新开奶奶留下的喫茶店，那家店以前是街上最热闹的地方之一。
- 记得: 小李小时候就在樱桥通长大，后来去了城市，现在又回来了。
- 记得: 奶奶去世后，喫茶店关了很久，现在终于又有人打算把灯重新点起来。
- 好像: 樱桥通不大，街上几家店彼此都认识，谁家有点动静很快就会传开。
```

这说明夜间 `kujo -> player` 的图记忆已经能通过多跳图路由拿到玩家背景长期记忆。

## 未做项

1. 没有跑完整午夜 `nightly_refresh()` 全量压测
2. 没有重新测午夜总耗时
3. 没有调整夜间并发池大小

## 结论

夜间基准印象刷新现在已经能复用白天同一套多跳图路由器，并且拥有独立的更宽松参数。

当前结构是：

1. 白天玩家对话：`player_dialogue`
2. 白天 NPC 闲聊：`npc_dialogue`
3. 夜间印象整理：`nightly_impression`

三者共享同一个图路由流程，但参数和路由偏好不同。
