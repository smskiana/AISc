> 设计方案: [2026-07-10_记忆驱动行为与印象决策重构_plan.md](2026-07-10_记忆驱动行为与印象决策重构_plan.md)

# 记忆驱动行为与印象决策重构 — 执行记录

## 完成时间
2026-07-10

## 本次完成内容

本次已经完成第一轮后端落地，把“图真源 + 基准印象 + 白天微调 + 状态收口”的骨架正式接进运行时。

这不是只写方案，而是已经完成以下能力的代码实现：

1. 数据库支持新的状态基线/漂移字段
2. 新增熟人印象表 `npc_impressions`
3. `StateManager` 成为状态统一写入入口
4. 夜间可批量生成基准印象与次日计划上下文
5. 行为计划和搭话决策开始读取印象与夜间摘要
6. 玩家对话 / NPC 对话结束后会对白天状态做即时微调

## 实际改动清单

### 修改文件 (8)

| 文件 | 实际改动 |
|------|------|
| `backend/src/database/sqlite_client.py` | 为 `npc_states` 增加 `emotion_baseline / emotion_delta / sociability_baseline / sociability_delta / lingering_concern / next_day_plan_context`；新增 `npc_impressions` 表；补旧存档自动迁移 |
| `backend/src/npc/state_manager.py` | 新增状态统一入口：`begin_new_day()`、`apply_tick()`、`apply_interaction_effect()`、`nightly_refresh()`；实现夜间基准印象生成、计划摘要生成、白天漂移合成 |
| `backend/src/dialogue/prompt_builder.py` | Prompt 从读 `bond` 改为读“当前印象 + 说话提示”；接入 `StateManager` 读取状态和印象 |
| `backend/src/memory/retrieval.py` | 检索路由 Prompt 去掉 `bond`，改为读取简短印象摘要 |
| `backend/src/npc/behavior_engine.py` | 注入 `StateManager`；新的一天改由状态层结算；`_plan_day()` 注入 `next_day_plan_context`；主动搭话判断改读印象；需求更新改走状态层 |
| `backend/src/npc/npc_dialogue.py` | NPC ↔ NPC 对话结束后生成互动摘要，并调用状态层更新白天微调 |
| `backend/src/application/dialogue_service.py` | 玩家对话结束后把互动总结提交给状态层，更新 NPC 的白天即时状态 |
| `backend/src/application/runtime.py` | 启动时接通 `StateManager` 到 Prompt / 行为 / 对话服务；午夜流程加入 `nightly_refresh()`；读档后重建相关接线 |

### 文档文件 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-10_记忆驱动行为与印象决策重构_plan.md` | 本次实施依据 |
| `docs/AIChanges/Memory/2026-07-10_记忆驱动行为与印象决策重构_execution.md` | 本执行记录 |

## 关键实现说明

### 1. `bond` 没有被立即硬删，但主决策链已不再依赖它

当前处理策略是：

- 旧表 `npc_bonds` 继续保留，避免一次性打爆兼容性
- 但新的行为 / Prompt / 检索主链已经改成优先读取：
  - `npc_impressions`
  - `npc_states` 中的基线与白天漂移

也就是说：

- `bond` 已经从“主决策输入”降级为“遗留兼容数据”

### 2. 状态层正式收口

这次已经把状态更新分成了三类入口：

1. `begin_new_day()`
   - 新的一天开始时重置为夜间结算后的基准状态
2. `apply_tick()`
   - 每个游戏分钟推进一次精力和轻量波动
3. `apply_interaction_effect()`
   - 对话结束后立刻把互动结果写成白天即时变化

这意味着：

- 行为层不再独自维护情绪语义
- 对话层不再自己偷偷改长期状态

### 3. 夜间新增两个重要产物

通过 `nightly_refresh()`，每个 NPC 在午夜后会得到：

1. `npc_impressions`
   - 对熟人的 `baseline_impression / speech_hint / approach_bias`
2. `npc_states.next_day_plan_context`
   - 供次日日计划 Prompt 注入的夜间摘要

这样白天就不需要高频深查整张图了。

### 4. 行为决策已经开始吃“记忆压缩结果”

落地点：

- `_plan_day()` 现在会读取 `next_day_plan_context`
- `_llm_decide_talk()` 现在会读取：
  - 当前印象
  - 说话提示
  - 接近倾向
  - 当前精力 / 社交开放度

这比之前只看 `personality + routine + bond` 明显更接近“有记忆的 NPC”。

### 5. 对话结束后会产生当天状态波动

落地点：

- 玩家 ↔ NPC 对话结束：`dialogue_service.py`
- NPC ↔ NPC 对话结束：`npc_dialogue.py`

两者都会把对话压成一条短摘要，交给 `StateManager.apply_interaction_effect()`，写入：

- `emotion_delta`
- `sociability_delta`
- `npc_impressions.delta_note`
- `npc_impressions.delta_bias`

这部分就是“白天微调”。

## 验证结果

### 已完成验证

- [x] Python 编译检查通过：
  - `backend/src/database/sqlite_client.py`
  - `backend/src/npc/state_manager.py`
  - `backend/src/dialogue/prompt_builder.py`
  - `backend/src/memory/retrieval.py`
  - `backend/src/npc/behavior_engine.py`
  - `backend/src/npc/npc_dialogue.py`
  - `backend/src/application/dialogue_service.py`
  - `backend/src/application/runtime.py`

- [x] 启动导入链检查通过：
  - `import src.main`
  - 返回 `import-ok`

- [x] 轻量 smoke test 通过：
  - 新建临时 SQLite
  - 执行 `StateManager.cold_start()`
  - 执行 `nightly_refresh(1)`
  - 执行 `begin_new_day("sakura")`
  - 验证 `npc_states` 新字段和 `npc_impressions` 记录可正常读写
  - 返回 `smoke-ok`

### 尚未做的联调验证

- [ ] 实际启动后端并运行到午夜，观察基准印象生成日志
- [ ] Unity 连接后查看 NPC 行为是否因 `next_day_plan_context` 出现可感知差异
- [ ] 玩家与 NPC 连续多轮对话后，确认第二次对话语气会体现白天微调
- [ ] NPC ↔ NPC 连续社交后，确认主动搭话倾向能被当天互动影响
- [ ] 旧存档升级后，确认 `npc_impressions` 缺失时首个午夜可自动补齐

## 当前已知限制

1. `bond` 还没有彻底清理
   - 当前是“停止作为主决策输入”，不是“数据库层完全删除”

2. 夜间基准印象生成虽然已经接入图和短期记忆，但仍偏轻量
   - 目前更像“第一版压缩视图”
   - 还不是完整的高级关系推导系统

3. 白天状态波动采用的是启发式关键词评分
   - 已能工作
   - 后续可以再换成更精细的互动结果分类

4. `BehaviorEngine` 仍然偏大
   - 这次优先完成能力接入
   - 还没有继续拆为更细的 planning / state / social 子层

## 结论

这次改动已经让系统从：

- “对话略有记忆，行为基本像无记忆规则机”

推进到：

- “夜间会整理熟人印象与次日摘要，白天行为和对话都开始读取这些结果，并且当天互动会反向改写即时状态”

也就是说，`图 → 印象 → 状态 → 行为/对话` 的主链已经开始成形。
