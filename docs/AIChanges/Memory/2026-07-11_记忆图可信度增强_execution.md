> 设计方案: [2026-07-11_记忆图可信度增强_plan.md](2026-07-11_记忆图可信度增强_plan.md)

# 记忆图可信度增强 — 执行记录

## 完成时间

2026-07-11

## 本次目标

补强当前记忆图系统的原型可信度：

1. 玩家真实行动能进入 NPC 记忆链。
2. 融合节点能追溯来源。
3. 检索质量和性能能统计。
4. 白天图路由减少不必要 LLM 调用。
5. 图调试接口能看见节点、边和诊断，而不只是 count。

## 实际改动

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/src/database/sqlite_client.py` | 新增 `memory_merge_sources` / `memory_retrieval_logs` 表与写入查询辅助 |
| `backend/src/memory/player_events.py` | 新增玩家事件写入器，把玩家真实行动写入 NPC 短期记忆 |
| `backend/src/application/services.py` | 服务容器新增 `player_events` |
| `backend/src/application/runtime.py` | 接入 `PLAYER_EVENT` 消息，返回 `PLAYER_EVENT_RECORDED` |
| `backend/src/memory/evolution.py` | 融合成功时写入来源追溯 |
| `backend/src/memory/retrieval.py` | 增加本地自信跳过 LLM；每次检索写诊断日志 |
| `backend/src/main.py` | `/api/npc/{npc_id}/graph` 支持 `detail=true&limit=...` |
| `backend/scripts/run_7day_benchmark.py` | summary 增加 `retrieval_metrics` 聚合 |
| `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-11.md` | 更新当前状态 |
| `docs/DesignDocs/MemoryArchitecture.md` | 更新第 32 节当前口径 |

### 新建文档

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-11_记忆图可信度增强_plan.md` | 本方案 |
| `docs/AIChanges/Memory/2026-07-11_记忆图可信度增强_execution.md` | 本执行记录 |

## 关键实现

### 1. `PLAYER_EVENT`

新增后端消息：

```json
{
  "type": "PLAYER_EVENT",
  "event_type": "cafe_progress",
  "content": "小李今天把奶奶留下的喫茶店门口打扫干净了。",
  "location_id": "player_cafe.doorway",
  "importance": 0.8,
  "witness_npcs": ["sakura"]
}
```

处理结果：

1. 指定 `witness_npcs` 时写入指定 NPC。
2. 未指定时写入同 zone / 相邻 zone 的 NPC。
3. 如果没有 NPC 在附近，则写给所有 NPC 一条“街上传闻”版本。
4. 写入 `short_term_memories(type='player_event')`。
5. 午夜仍走现有 `extract_and_ingest()` 入图，不建立独立硬事实库。

### 2. 融合来源追溯

新增 `memory_merge_sources`。

融合成功时记录：

1. `merged_node_id`
2. `source_node_id`
3. `source_type`
4. `source_value`
5. `similarity`
6. `created_at_game_time`

### 3. 检索诊断

新增 `memory_retrieval_logs`。

每次成功检索记录：

1. `graph_nodes`
2. `vector_fallback`
3. `final_nodes`
4. `selected_edges`
5. `llm_route_calls`
6. `local_route_skips`
7. `hit_merged_count`
8. `elapsed_sec`

### 4. 本地路由跳过 LLM

每种检索模式新增保守阈值：

1. `local_route_min_score`
2. `local_route_margin`

如果本地排序 top N 明显优于下一名，则直接走本地结果，避免不必要 LLM 路由。

### 5. 图调试接口

旧调用仍兼容：

```text
GET /api/npc/sakura/graph
```

新增 detail：

```text
GET /api/npc/sakura/graph?detail=true&limit=50
```

返回：

1. `nodes`
2. `edges`
3. `merge_sources`
4. `recent_retrievals`

## 验证

### 1. Python 编译

执行：

```powershell
python -m py_compile backend/src/database/sqlite_client.py backend/src/memory/player_events.py backend/src/application/services.py backend/src/application/runtime.py backend/src/memory/evolution.py backend/src/memory/retrieval.py backend/src/main.py backend/scripts/run_7day_benchmark.py
```

结果：通过。

### 2. 隔离 smoke

使用临时 SQLite，不碰真实存档。

验证点：

1. `memory_merge_sources` 表存在。
2. `memory_retrieval_logs` 表存在。
3. `PlayerEventMemoryWriter` 可写入玩家事件短期记忆。
4. 没有附近 NPC 时，事件以传闻模式写入 5 个 NPC。
5. 融合来源可写入并查询。
6. 检索日志可写入并查询。
7. `_can_use_local_route()` 在分差足够时返回 True。

smoke 输出摘要：

```text
player_event_written: success=True, written=[sakura,chihaya,kazuha,tatsunosuke,kujo], rumor_mode=True
stm_count: 5
merge_sources: 1
retrieval_log: llm=0, local=1
```

## 未完成项

1. Unity 前端还没有正式的 `SendPlayerEvent()` 调用点；后续需要在任务/互动系统触发。
2. `PLAYER_EVENT` 当前先写短期记忆，仍需到午夜才入图；如果未来需要“玩家刚做完立刻能被 NPC 提到”，要加白天即时入图或即时短期检索。
3. 检索诊断已经写库，但还没有做可视化面板。
4. 融合来源已可追溯，但还没有 UI 展开来源。
5. 本地跳过 LLM 的阈值需要后续长测调参。

## 结论

记忆图现在从“能跑通”增强为“更可诊断、更能承接玩家真实事件”的状态。

最关键变化是：

```text
玩家真实行动
→ PLAYER_EVENT
→ NPC 短期记忆
→ 午夜提取入图
→ Day N 新记忆自然更新 Day 0 传闻
```

同时，融合和检索都开始留下可观察数据，后续跑测能更精确地判断记忆系统是不是在按设计工作。
