# 2026-07-11: 旧表索引早于迁移导致启动失败

## 现象

前端开始界面无法连上后端。手动实例化 `SQLiteClient("backend/data/game.db")` 时抛出：

```text
sqlite3.OperationalError: no such column: clarity_ab
```

后端旧日志还出现：

```text
sqlite3.OperationalError: no such column: emotion_delta
```

## 根本原因

`SQLiteClient._init_db()` 先执行完整 `SCHEMA_SQL`，再执行 `_apply_migrations()`。

当真实旧库里已经存在旧版 `memory_edges` 表时，`CREATE TABLE IF NOT EXISTS memory_edges (...)` 不会改表结构；随后同一段 schema 继续执行：

```sql
CREATE INDEX IF NOT EXISTS idx_edges_clarity
ON memory_edges(clarity_ab DESC, clarity_ba DESC);
```

由于旧表还没有 `clarity_ab / clarity_ba`，索引创建直接失败，后面的正式迁移没有机会运行。

## 错误模式

以下模式高风险：

1. `CREATE TABLE IF NOT EXISTS` 之后立即创建依赖新增列的索引。
2. 迁移函数放在完整 schema 执行之后。
3. 旧表包含历史必填列，新代码插入时只写新 schema 的少数字段。
4. 读档把旧数据库覆盖回运行库，但覆盖后没有重新执行迁移。

## 正确做法

启动初始化要分层：

1. 先执行“预迁移”，只补齐会阻断 schema/index 的关键列。
2. 再执行完整 schema 和索引。
3. 再执行普通迁移，补齐业务新增字段和新增表。
4. 对无法轻易删改的旧表，插入逻辑需要根据真实列做兼容，或专门重建表。
5. 存档恢复后也要立即执行同一套迁移，不能只在后端进程启动时迁移。

## 适用范围

重点关注：

1. SQLite 表结构演进。
2. 新增索引依赖新增列。
3. 旧存档 / 旧数据库热升级。
4. `CREATE TABLE IF NOT EXISTS` 被误以为能自动补列的场景。

## 修改前自查问题

1. 这个索引依赖的列，在旧库里一定存在吗？
2. `CREATE TABLE IF NOT EXISTS` 是否只是跳过旧表，而不是升级旧表？
3. 迁移失败时，后端是否会在前端看来表现成“连接不上”？
