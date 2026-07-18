> 设计方案: [2026-07-09_记忆检索与对话链路修复_plan.md](2026-07-09_记忆检索与对话链路修复_plan.md)

# 记忆检索与对话链路修复 — 执行记录

## 完成时间
2026-07-09

## 实际改动清单

### 修改文件 (6)

| 文件 | 实际改动 |
|------|------|
| `backend/src/dialogue/prompt_builder.py` | 修复 `_parse_day` 调用方式；NPC 对话检索上下文限制改为 2 条 |
| `backend/src/database/lancedb_client.py` | 批量写入改为“读取旧表 + 按 `node_id` 合并 + overwrite”；单条写入复用批量逻辑 |
| `backend/src/main.py` | 补齐全局 `lancedb`；修复 `npc_memories` 调试接口，按 v0.6 schema 返回基础节点并尽量补全 LanceDB 字段 |
| `backend/src/memory/retrieval.py` | 检索起点改为“我 + 对方 person 节点”，无 LanceDB 时安全回退 |
| `backend/src/npc/behavior_engine.py` | 新增绝对游戏分钟计算；修复 NPC 社交冷却跨天问题；顺手修正 P6 冷却同类问题 |
| `Assets/Scripts/Core/GameManager.cs` | `PLAYER_CHOICE` 发送前增加 JSON 字符串转义，避免引号/换行破坏请求体 |

### 新建文档 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-09_记忆检索与对话链路修复_plan.md` | 本次修复方案 |
| `docs/AIChanges/Memory/2026-07-09_记忆检索与对话链路修复_execution.md` | 本执行记录 |

## 关键修复说明

### 1. 对话入口不再因 `_parse_day` 崩溃
- 玩家对话 `PromptBuilder.build()` 原来会因 `self._parse_day` 抛 `AttributeError`
- NPC ↔ NPC 轻量记忆构建也有同样问题
- 已统一改回模块级 `_parse_day(...)`

### 2. LanceDB 不再用新批次覆盖整表
- 原实现每次 `upsert_nodes()` 都只把“本次节点”写回表
- 现在先读取旧表，再按 `node_id` 覆盖合并，最后整表回写
- 这样午夜提取和后续增量写入不会把历史向量数据抹掉

### 3. `main.py` 的 `lancedb` 生命周期统一
- 原来 `lifespan()` 里创建的是局部变量
- 对话结束与玩家记忆提取路径访问的是未声明全局
- 现在已统一为全局服务实例

### 4. 社交冷却改为跨天绝对分钟
- 原来只存 `hour * 60 + minute`
- 次日分钟归零后会导致旧冷却残留
- 现在改为 `(day - 1) * 1440 + hour * 60 + minute`

### 5. 调试接口兼容 v0.6 schema
- `/api/npc/{npc_id}/memories` 不再按不存在的 `energy` 排序
- 会优先返回 SQLite 节点，再尽可能补上 LanceDB 中的 `type/value/importance/archived`

### 6. 检索起点更接近设计文档
- 从“我”节点和“对方人物节点”启动
- 如果 LanceDB 不可用，再回退到最基本的可检索节点

### 7. Unity 对话选项发送更稳
- 选项含双引号、换行、反斜杠时不再破坏 JSON 请求体

## 验证情况

### 已完成
- [x] 修复文档已写入 `docs/AIChanges/`
- [x] Python 语法编译检查通过：
  - `backend/src/main.py`
  - `backend/src/dialogue/prompt_builder.py`
  - `backend/src/database/lancedb_client.py`
  - `backend/src/memory/retrieval.py`
  - `backend/src/npc/behavior_engine.py`

### 未完成 / 需你本地联调确认
- [ ] Unity Editor 编译检查
- [ ] 玩家点 NPC 开始对话，确认不再出现 Prompt 构建错误
- [ ] 对话结束后玩家记忆提取链路确认
- [ ] 连续跨天运行，确认 NPC 社交冷却次日恢复正常
- [ ] 午夜提取多次执行后，确认 LanceDB 历史记忆未被新批次覆盖

## 备注

1. 本次修复遵循“最小修改”原则，没有重构记忆系统和消息框架
2. `LanceDBClient` 目前仍采用“小表整表重写”的合并策略，性能一般，但已显著优于“直接覆盖丢历史数据”
3. `behavior_engine.py` 中还存在一处重复 `continue` 的旧代码，但它不影响本次修复目标，因此未顺手扩改
