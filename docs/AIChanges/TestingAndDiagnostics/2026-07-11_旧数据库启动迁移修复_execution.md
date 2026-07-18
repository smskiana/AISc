> 设计方案: [2026-07-11_旧数据库启动迁移修复_plan.md](2026-07-11_旧数据库启动迁移修复_plan.md)

# 旧数据库启动迁移修复 — 执行记录

## 完成时间

2026-07-11

## 问题现象

前端开始界面无法启动后端并连接。后端日志里有旧错误：

```text
sqlite3.OperationalError: no such column: emotion_delta
```

手动实例化真实库 `backend/data/game.db` 时进一步定位到：

```text
sqlite3.OperationalError: no such column: clarity_ab
```

## 根本原因

真实 `game.db` 仍保留旧版图记忆表：

1. `memory_edges` 只有 `weight_ab / weight_ba`，没有 `clarity_ab / clarity_ba / target_importance`。
2. `memory_nodes` 仍有旧版必填字段 `type / value`。
3. `SQLiteClient._init_db()` 先执行完整 `SCHEMA_SQL`，其中 `idx_edges_clarity` 索引依赖 `clarity_ab / clarity_ba`，导致正式迁移函数还没执行就失败。

## 实际改动

### `backend/src/database/sqlite_client.py`

1. 新增 `_apply_pre_schema_migrations()`。
   - 在执行完整 `SCHEMA_SQL` 前，先为旧 `memory_edges` 补齐：
     - `clarity_ab`
     - `clarity_ba`
     - `target_importance`
   - 若旧表存在 `weight_ab / weight_ba`，同步回填到 clarity 字段。
2. 新增 `_table_exists()` 与 `_table_columns()`。
   - 供预迁移和兼容插入读取真实表结构。
3. 调整 `insert_node()`。
   - 根据真实 `memory_nodes` 列动态补写旧 schema 的 `type / value` 必填字段。
   - 避免旧库冷启动或重建图节点时插入失败。

### `backend/src/save/manager.py`

1. `load()` 在 SQLite 备份恢复后立即调用 `_migrate_restored_database()`。
2. 新增 `_migrate_restored_database()`。
   - 对恢复后的 `backend/data/game.db` 重新实例化 `SQLiteClient`，复用启动迁移逻辑。
   - 避免旧存档读档后把运行库覆盖回旧 schema。
   - 迁移失败时返回 `None`，让上层按存档不可用处理。

### 错误预防文档

1. 新增：
   - `docs/DesignDocs/errors/2026-07-11_schema_index_before_migration.md`
2. 更新：
   - `docs/DesignDocs/ErrorPreventionIndex.md`

## 验证结果

1. Python 编译通过：

```powershell
python -m py_compile backend/src/database/sqlite_client.py backend/src/application/runtime.py backend/src/main.py backend/run.py
```

2. 真实库迁移通过：

```text
SQLiteClient("backend/data/game.db") -> migrated
```

3. 关键表字段确认存在：

```text
npc_states: emotion_delta / sociability_delta / next_day_plan_context 已存在
memory_edges: clarity_ab / clarity_ba / target_importance 已存在
memory_merge_sources / memory_retrieval_logs 已存在
```

4. 兼容插入 smoke 通过：

```text
npc_states 写入 emotion_delta=0.0 成功
memory_nodes 旧表兼容插入 node_smoke 成功
```

5. 后端启动成功：

```text
REST http://127.0.0.1:8766
WS   ws://127.0.0.1:8766/ws
```

6. Health 检查通过：

```json
{"status":"ok","version":"0.2.0"}
```

7. 存档列表链路通过：

```json
{"type":"SAVES_LIST","saves":[{"slot":"test1","game_day":1,"version":"0.2.0"}]}
```

8. 旧存档读档迁移通过：

```text
SaveManager.load("test1") -> loaded True
恢复后的 game.db 仍包含 emotion_delta / clarity_ab / clarity_ba / target_importance
```

9. 前端入口等价链路通过：

```json
{"type":"LOAD_COMPLETE","game_time":{"day":1,"hour":8,"minute":0,"weather":"sunny"}}
```

```json
{"type":"GAME_READY","mode":"CONTINUE","fresh_start":false}
```

## 结论

本次不是存档 manifest 损坏，而是旧 `game.db` schema 热升级顺序错误导致后端无法稳定启动；同时旧存档读档后也需要立刻迁移。修复后，后端已能启动，开始界面所需的 health、`GET_SAVES`、`LOAD_REQUEST`、`GAME_START CONTINUE` 链路均可返回。

当前手动验证启动的后端进程为：

```text
PID 7680
```
