> 设计方案: [2026-07-10_跑测问题修复_plan.md](2026-07-10_跑测问题修复_plan.md)

# 跑测问题修复 — 执行记录

## 完成时间
2026-07-10

## 本次完成内容

这次不是只写计划，而是已经把计划里的第一批核心修复直接落到了代码里，并做了轻量验证。

本轮实际完成的是：

1. 统一后端控制台与文件日志为 UTF-8
2. 为 Unity 可视化消息新增单独日志文件，便于无前端时复盘
3. 调整记忆检索排序，让“当前目标人物直接相关”的事件更容易排到前面
4. 把检索后的 `clarity` 恢复闭环真正接上
5. 增强人物/情绪节点复用，并补强弱连接事件和 `felt` 情绪覆盖

## 实际修改文件

| 文件 | 实际改动 |
|------|------|
| `backend/run.py` | 统一 `stdout/stderr` 为 UTF-8；新增 `backend/logs/backend.log` UTF-8 文件日志 |
| `backend/src/application/message_bus.py` | 新增 `backend/logs/unity_messages.log`；`NPC_BUBBLE/NPC_SOCIAL_ACTION` 在 `active/broadcast` 两条链都落盘，并标记 `live/fallback` |
| `backend/src/application/runtime.py` | `init_retrieval(...)` 与 `_refresh_vector_services()` 都注入 `clarity_recover=mem_mgr.recover_clarity` |
| `backend/src/memory/retrieval.py` | 补充目标人物偏置排序、向量结果二次细排、最终命中图边 `clarity` 恢复 |
| `backend/src/memory/manager.py` | 增加情绪关键词补强、人物/情绪节点复用、弱连接事件补边与诊断日志 |

## 关键实现说明

### 1. UTF-8 日志链路

1. 后端入口现在会在启动时统一配置 UTF-8 输出
2. 后端主日志落到 `backend/logs/backend.log`
3. Unity 相关消息额外落到 `backend/logs/unity_messages.log`
4. 即使 C# 侧没启动，也能在日志里直接看到 NPC 气泡与社交动作

### 2. 检索更偏“当前正在想的那个人”

1. 图召回会记录候选是否直接来自目标人物起点
2. 合并排序阶段会给 `source_is_target`、`involved + ba` 等熟人相关信号加权
3. 纯 `relationship -> person` 候选会被轻量降权，避免空泛人物节点挤占前排
4. 向量结果在入列前还会再按目标人物相关性做一次细排

### 3. clarity 恢复闭环

1. 检索阶段会记录真正参与回忆的图边
2. 最终进入结果的高优先边会调用 `recover_clarity()`
3. 这样“经常被想起的人和事”不再只是衰减，也会逐步变稳

### 4. 入图结构补强

1. `person/self/emotion` 节点优先复用，而不是每次重新造点
2. 事件文本里有明显情绪词但 LLM 没抽到时，会启发式补一个基础情绪节点
3. 对没有任何连接的新事件节点，会自动补一条 `event -> self` 的 `involved`
4. 写入后会记录 `weak_nodes`，方便继续诊断图是否还在长孤点

## 验证结果

### 代码与导入检查

1. `python -m py_compile` 已通过：
   - `backend/run.py`
   - `backend/src/application/message_bus.py`
   - `backend/src/application/runtime.py`
   - `backend/src/memory/retrieval.py`
   - `backend/src/memory/manager.py`
2. `import src.main` 已通过，输出 `import ok`

### 定向 smoke 结果

1. `written_nodes = 2`
2. 检索首条结果已经变成新近且目标人物相关的事件：
   - `我晚上和千早一起试做了新口味面包，聊得很开心。`
3. `clarity_before_ba = 0.756`
4. `clarity_after_ba = 0.778`
5. `person_node_count_for_chihaya = 1`
6. `happy_emotion_nodes = 1`
7. `unity_log_tail` 已写入：
   - `13:46:34 [fallback] [broadcast] NPC_BUBBLE sakura -> chihaya: 今晚的新面包好像很成功。`

### 本轮补充验证

1. 重新执行轻量日志 smoke 后，`backend/logs/backend.log` 可被创建
2. `backend/logs/unity_messages.log` 继续以 UTF-8 正常追加：
   - `13:49:44 [fallback] [broadcast] NPC_BUBBLE sakura -> chihaya: UTF-8 日志检测：今晚的新面包很顺利。`

## 额外现象

1. 定向 smoke 末尾仍出现过一次 `Loading weights...`
2. 这说明某处仍会触发真实 embedding 模型加载
3. 目前不影响这轮修复目标，但之后继续做长跑前值得再查一次缓存与初始化路径

## 本轮未继续做的事

1. 新的 7 天完整跑测这轮先没有重跑
2. 午夜耗时优化的收益对比也还没重新量化
3. 这两项建议放到下一轮，在当前修复版本上统一复测
