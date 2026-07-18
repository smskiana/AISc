# 无前端对话日志回退 — 执行记录

## 完成时间
2026-07-10

## 修改目的

当 Unity/C# 没有启动或没有连接 WebSocket 时，NPC ↔ NPC 的社交动作和气泡对白虽然已经由后端生成，但默认只会进入消息总线队列，终端里看不到具体内容。

这次做一个单文件小修，让关键对话可视化消息在“没有接收端”时自动写入后端日志，方便纯后端跑测时直接观察。

## 实际改动

### 修改文件 (1)

| 文件 | 改动 |
|------|------|
| `backend/src/application/message_bus.py` | 增加 `sakurabashi.message_bus` 日志器；当没有活动 WS 连接时，额外将 `NPC_SOCIAL_ACTION` 和 `NPC_BUBBLE` 写入日志；后续修正 `NPC_SOCIAL_ACTION` 回退日志读取字段为 `npc_id / target_npc_id` |

## 日志行为

当前仅对以下消息做日志回退：

1. `NPC_SOCIAL_ACTION`
2. `NPC_BUBBLE`

这样可以避免把所有时钟、状态同步消息都刷进日志，保持重点清晰。

输出格式示例：

```text
[无C#接收] NPC_SOCIAL_ACTION sakura <-> chihaya @ flower_shop.doorway (测试)
[无C#接收] NPC_BUBBLE sakura -> chihaya: 今天辛苦啦。
```

## 验证结果

- [x] `backend/src/application/message_bus.py` 编译通过
- [x] 构造 `MessageBus` 无活动连接时手动 `broadcast()`：
  - `NPC_SOCIAL_ACTION` 会写入日志
  - `NPC_BUBBLE` 会写入日志
  - 无关消息如 `GAME_TIME_UPDATE` 不会额外写日志

- [x] 实际后端跑测验证过 `NPC_BUBBLE` 会落到日志
  - 在 1 天纯后端运行里，日志出现了无前端接收时的对白输出
  - 例如：
    - `NPC_BUBBLE kazuha -> tatsunosuke: ...`
    - `NPC_BUBBLE tatsunosuke -> kazuha: ...`

- [x] 跑测中发现并修正 `NPC_SOCIAL_ACTION` 字段名问题
  - 第一版日志回退读取了不存在的 `npc_a / npc_b`
  - 实际 payload 使用的是 `npc_id / target_npc_id`
  - 已改正

## 说明

这次属于单文件小修，因此没有单独写 `_plan.md`，直接补执行记录。
