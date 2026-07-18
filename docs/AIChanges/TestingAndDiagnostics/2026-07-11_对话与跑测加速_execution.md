> 设计方案: [2026-07-11_对话与跑测加速_plan.md](2026-07-11_对话与跑测加速_plan.md)

# 对话与跑测加速 — 执行记录

## 完成时间

2026-07-11

## 实际改动清单

### 修改文件 (6)

| 文件 | 实际改动 |
|------|------|
| `backend/src/application/dialogue_service.py` | 玩家建议回复改为后台异步推送；`DIALOGUE_COMPLETE` 先返回兜底建议；对话结束时 NPC 短期记忆和玩家向量记忆改为一次结构化摘要；新增对话性能与玩家记忆写入日志 |
| `backend/src/application/message_bus.py` | HTTP 轮询队列默认关闭，仅通过 `SAKURA_ENABLE_POLL_QUEUE=1` 开启；WebSocket 直推保留为主链 |
| `backend/src/memory/retrieval.py` | 多跳检索新增 `[MEMORY]` 与 `[PERF]` 日志，标记图命中、向量兜底、最终节点数与耗时 |
| `backend/src/application/runtime.py` | 午夜各阶段日志改为统一 `[PERF] midnight_stage=...` / `[PERF] midnight_total` |
| `Assets/Scripts/Data/MessageTypes.cs` | 新增 `DIALOGUE_CHOICES_UPDATE` 消息类型与回调 |
| `Assets/Scripts/Core/GameManager.cs` | 接收 `DIALOGUE_CHOICES_UPDATE` 后刷新当前对话选项 |

### 新建文档 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/TestingAndDiagnostics/2026-07-11_对话与跑测加速_plan.md` | 本次方案 |
| `docs/AIChanges/TestingAndDiagnostics/2026-07-11_对话与跑测加速_execution.md` | 本执行记录 |

## 关键实现说明

### 1. 玩家建议回复不再阻塞 NPC 回复完成

旧流程：

1. NPC 流式回复结束
2. 等三条玩家建议 LLM 请求完成
3. 发送 `DIALOGUE_COMPLETE`

新流程：

1. NPC 流式回复结束
2. 立刻发送 `DIALOGUE_COMPLETE`，携带兜底建议
3. 后台异步生成真实建议
4. 完成后推送 `DIALOGUE_CHOICES_UPDATE`

这会降低玩家看到 NPC 回复完成的尾延迟。

### 2. 对话结束摘要从两次 LLM 降为一次 LLM

旧流程：

1. 一次 LLM 生成 NPC 第一人称短期记忆
2. 一次 LLM 生成玩家向量记忆摘要

新流程：

1. 一次 LLM 输出 JSON：

```json
{
  "npc_memory": "...",
  "player_memory": "..."
}
```

2. `npc_memory` 写入 NPC 短期记忆
3. `player_memory` 编码后写入玩家向量记忆

失败时仍有本地 fallback。

### 3. HTTP 轮询队列默认关闭

`MessageBus.broadcast()` 现在默认只走 WebSocket 直推，不再把每条消息都塞入 HTTP 轮询队列。

如需调试旧接口，可设置：

```powershell
$env:SAKURA_ENABLE_POLL_QUEUE='1'
```

### 4. 跑测日志标签

新增/统一以下日志标签：

1. `[PERF] player_dialogue_reply`
2. `[PERF] player_reply_choices`
3. `[PERF] dialogue_end_summary`
4. `[PERF] retrieve`
5. `[PERF] midnight_stage=...`
6. `[PERF] midnight_total`
7. `[MEMORY] retrieve`
8. `[MEMORY] player_memory_write`
9. `[WS] poll_queue_enabled=0/1`

下一轮跑测可以直接按这些标签筛日志。

## 验证结果

### Python 编译

已通过：

1. `backend/src/application/dialogue_service.py`
2. `backend/src/application/message_bus.py`
3. `backend/src/memory/retrieval.py`
4. `backend/src/application/runtime.py`

### 后端 smoke：玩家建议异步推送

使用假 LLM / 假 WS 验证消息顺序：

```text
['DIALOGUE_TOKEN', 'DIALOGUE_TOKEN', 'DIALOGUE_COMPLETE', 'DIALOGUE_CHOICES_UPDATE']
```

结果符合预期：

1. `DIALOGUE_COMPLETE` 先到
2. `DIALOGUE_CHOICES_UPDATE` 后到
3. 前者带兜底建议，后者带真实建议

### 后端 smoke：对话结束一次摘要

使用假 LLM 验证 `_summarize_dialogue_once()` 输出：

```python
{
    "npc_memory": "我和小李聊了奶奶的喫茶店。",
    "player_memory": "九条莲记得奶奶的喫茶店和商店街旧事。"
}
```

结果符合预期。

## 未完成项

1. 未执行 Unity Editor 编译
2. 未启动完整后端 + Unity 联调
3. 未跑完整 7 天压测

## 下一步跑测建议

跑测时重点观察：

1. `player_dialogue_reply` 和 `player_reply_choices` 是否分离
2. `dialogue_end_summary` 是否明显少一次 LLM 请求耗时
3. `retrieve` 的 `graph_nodes / vector_fallback / final_nodes` 是否能证明 NPC 记忆链可用
4. `midnight_stage=impression_state` 是否因夜间多跳变慢，需要继续调 `nightly_impression` 参数
