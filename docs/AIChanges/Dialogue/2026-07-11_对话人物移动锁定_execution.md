> 设计方案: [2026-07-11_对话人物移动锁定_plan.md](2026-07-11_对话人物移动锁定_plan.md)

> 历史状态提示：本文只记录当时的移动锁阶段。当前 NPC-NPC 社交已升级为 PREPARE / READY / FAILED / COMPLETE 闭环，请从 `docs/Workstreams/Dialogue/README.md` 进入。

# 对话人物移动锁定 — 执行记录

## 完成时间

2026-07-11

## 本次目标

修复“人物对话时还在乱动”的前端表现问题。

重点覆盖两种对话：

1. 玩家与 NPC 的正式立绘对话。
2. NPC 与 NPC 的头顶气泡对话。

## 实际改动

### 修改脚本

| 文件 | 改动 |
|------|------|
| `Assets/Scripts/Core/GameManager.cs` | 新增 `OnDialogueEnded` 事件，让正式对话结束也能通知外部释放锁 |
| `Assets/Scripts/NPC/NpcEntity.cs` | 新增 NPC 移动锁、pending move、解锁后执行最后一次移动 |
| `Assets/Scripts/NPC/IMovementProvider.cs` | 移动协程识别 `NpcEntity.IsMotionLocked`，锁定时暂停 elapsed |
| `Assets/Scripts/Dialogue/NpcBubbleManager.cs` | NPC 气泡会话播放期间锁定双方；正式对话开始/结束锁定和释放目标 NPC |

### 新建文档

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Dialogue/2026-07-11_对话人物移动锁定_plan.md` | 本方案 |
| `docs/AIChanges/Dialogue/2026-07-11_对话人物移动锁定_execution.md` | 本执行记录 |

## 关键实现

### 1. NPC 移动锁

`NpcEntity` 现在支持：

1. `PushMotionLock(reason)`
2. `PopMotionLock(reason)`
3. `IsMotionLocked`

锁定期间调用 `MoveToLocation()` 不会立刻移动，而是暂存最后一次目标地点。

解锁后只执行最后一次 pending move，避免对话结束后把对话期间积压的多段路径逐段跑完。

### 2. 已经在路上的 NPC 会冻结

`LerpMovementProvider.MoveRoutine()` 现在同时检查：

1. `GameManager.Instance.IsDialogueActive`
2. `NpcEntity.IsMotionLocked`

任一成立时不累计 `elapsed`，所以走到一半的 NPC 会停在原地，直到解锁。

### 3. NPC 气泡会话锁双方

`NpcBubbleManager` 在一组 NPC 气泡会话开始显示时：

1. 根据 conversation key 锁定 speaker + target。
2. 队列播完后释放双方。
3. 玩家打开正式对话时，清掉相关气泡队列并释放 NPC 气泡锁。

同时，`NPC_SOCIAL_ACTION` 不再为了对话强行 `MoveToLocation()`，只播放动作表现，避免“刚要说话人先乱跑”。

### 4. 玩家正式对话锁当前 NPC

`GameManager` 新增 `OnDialogueEnded`。

`NpcBubbleManager` 现在会：

1. `OnDialogueStarted` 时锁定当前 NPC。
2. `OnDialogueEnded` 时释放当前 NPC。

这样正式对话期间，即使该 NPC 之前在 NPC 气泡会话或移动途中，也不会在 UI 开着时恢复移动。

## 验证

### Unity 脚本校验

使用 Unity MCP `validate_script` 校验：

| 文件 | 结果 |
|------|------|
| `Assets/Scripts/Core/GameManager.cs` | 0 error / 1 warning |
| `Assets/Scripts/NPC/NpcEntity.cs` | 0 error / 0 warning |
| `Assets/Scripts/NPC/IMovementProvider.cs` | 0 error / 0 warning |
| `Assets/Scripts/Dialogue/NpcBubbleManager.cs` | 0 error / 0 warning |

`GameManager.cs` 的 warning 是既有字符串拼接 GC 提示，不是本轮编译错误。

### Unity Console

读取 error / warning：

1. 未发现脚本编译 error。
2. 仅出现一次 MCP batch 工具提示，与项目脚本无关。

## 未完成项

1. 尚未做 Unity Play 模式肉眼验证，需要实际观察 NPC 气泡对话期间双方是否稳定停住。
2. 当前只保证“对话期间不乱动”，不做“先靠近再对话”的社交站位系统。
3. pending move 只保留最后一次目标地点；如果后续需要完整路径表现，应单独设计行为队列可视化。
