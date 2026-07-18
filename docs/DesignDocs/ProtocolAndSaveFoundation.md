# 协议与存档底座

## 1. 系统边界

### Unity 权威状态

- 玩家位置、属性、背包、货币
- 游戏时间、天气、世界进度、任务
- NPC 逻辑位置、基础数值、日程结果
- 未来经营、交易、耕种等玩法事实

### Python 权威状态

- NPC 长短期记忆
- 记忆节点、关系边与 clarity
- 向量索引和记忆检索元数据
- 由记忆系统产生且仅服务记忆推理的派生数据

### 不进入长期存档

- Transform 连续坐标、动画播放进度和 UI 显隐
- 进行中的移动、对话流、LLM 调用和后台协程
- 请求超时器、临时锁、连接 session 和消息 sequence

## 2. 标识符

- `slot_id`: 玩家可选择的稳定存档槽 ID。
- `save_id`: 一个存档系列的稳定 ID，可跨多次覆盖保存。
- `checkpoint_id`: 一次保存尝试产生的唯一 ID，Unity 与 Python 必须一致。
- `request_id`: 一次协议命令的唯一 ID，用于关联、重试和幂等。
- `session_id`: 一次 WebSocket 连接会话 ID。

跨端标识符使用小写英文、数字和下划线；UUID 内容去除连字符后仍符合稳定 ID 规则。

## 3. 协议 envelope

```json
{
  "protocol_version": 1,
  "type": "memory_checkpoint_prepare",
  "request_id": "req_0123",
  "session_id": "session_0123",
  "sequence": 42,
  "sent_at": "2026-07-14T12:00:00Z",
  "payload": {},
  "error": null,
  "warnings": []
}
```

错误结构统一包含稳定 `code`、显示 `message`、`retryable` 和结构化 `details`；业务逻辑不得解析显示文本。

## 4. 消息可靠性

| 等级 | 要求 | 示例 |
|------|------|------|
| 幂等命令 | 相同 `request_id` 不重复产生副作用 | 保存、加载、玩家事件、NPC 终态 |
| 有序流 | 校验 `session_id + sequence` | 对话 token、快照增量 |
| 可丢事件 | 允许断线丢失 | 心跳、诊断、临时表现 |
| 全量状态 | 重连后覆盖缓存 | Unity 世界快照、记忆检查点身份 |

## 5. 存档结构

逻辑结构如下，物理目录允许分开：

```text
slot_1/
  unity/
    world.json
    manifest.json
  memory/
    game.db
    lancedb/
    manifest.json
  save_manifest.json
```

总 manifest 至少包含 `slot_id`、`save_id`、`checkpoint_id`、`created_at`、`game_build`、Unity schema version、memory schema version 和双方摘要。

## 6. 保存事务

1. Unity 冻结会产生持久事实的入口。
2. Unity 生成 `checkpoint_id` 并写主存档临时文件。
3. Unity 发送 `memory_checkpoint_prepare`。
4. Python 将记忆数据库和 LanceDB 写入临时检查点并返回摘要。
5. Unity 校验后提交主存档与总 manifest。
6. Unity 发送 `memory_checkpoint_commit`。
7. 任一步失败发送 abort，并保留上一份完整检查点。

## 7. 加载事务

1. Unity 验证主存档、总 manifest 和本地摘要。
2. Unity 请求 Python prepare load 对应 `checkpoint_id`。
3. Python 在临时恢复区验证并迁移记忆数据库，不直接破坏当前运行数据。
4. 双方验证成功后取消临时运行任务。
5. Python 提交记忆检查点，Unity 应用主世界状态。
6. Unity 发送全量世界快照覆盖 Python 推理缓存。
7. 双方确认后恢复游戏输入和时间。

## 8. 重连

1. Unity 发送 `hello`，携带协议版本、当前 `checkpoint_id`、世界 revision 和最后确认 sequence。
2. Python 返回协商版本、当前记忆检查点和可恢复请求摘要。
3. 身份匹配时 Unity 发送全量世界快照；身份不匹配时停止自动恢复并返回稳定错误。
4. 进行中的对话、移动和 LLM 流默认取消；已提交的幂等命令可返回缓存结果。

## 9. 兼容迁移

1. 第一阶段解析器同时接受旧扁平消息和新 envelope。
2. 先迁移握手、保存、加载和世界快照，再迁移行为与对话消息。
3. Python 现有 `game_state`、`npc_states`、`player_inventory` 暂时保留；每迁移一个功能，明确其降为缓存或删除的退出条件。
4. 旧 SQLite 恢复继续遵循预迁移、schema/index、普通迁移顺序。

## 10. 代码职责

### Unity

- `WebSocketClient`: 连接和文本收发。
- `ProtocolClient`: envelope、sequence、请求关联和兼容解析。
- `GameCommandSender`: 业务命令构造。
- `UnitySaveRepository`: Unity 主存档磁盘读写。
- `SaveCoordinator`: 双端保存和加载事务。

### Python

- `ProtocolCodec`: envelope 编解码和旧格式适配。
- `ProtocolSession`: session、sequence 和版本协商。
- `RequestDeduplicator`: 幂等结果缓存。
- `MemoryCheckpointService`: 记忆检查点原子保存、验证和恢复。
- 业务 handler: 只处理对应消息，不承担传输规则。

## 11. NPC-NPC 社交协议

1. Python 发送 `NPC_SOCIAL_PREPARE`，不得同时生成或记录对话内容。
2. Unity 同时移动双方，并以真实 `MovementResult`、共同逻辑地点和物理距离决定 `READY` 或 `FAILED`。
3. 会合监督 deadline 为 120 秒，使用真实时间，不受游戏暂停和倍速影响。
4. Python 仅在 `NPC_SOCIAL_READY` 后调用 LLM；所有 `NPC_BUBBLE` 携带同一 `request_id`、`line_index` 和 `line_count`。
5. Unity 最后一句显示完成后发送 `NPC_SOCIAL_COMPLETE`。
6. Python 只在 COMPLETE 后写短期记忆和互动影响；FAILED、CANCEL、断线和超时均不得写成已发生事实。
7. 玩家正式对话可以抢占准备中或播放中的 NPC-NPC 会话，Unity 必须回报 FAILED 并释放移动锁。
8. 旧 `NPC_SOCIAL_ACTION` 和无 `request_id` 气泡只用于旧消息兼容，不得作为新功能参考实现。
