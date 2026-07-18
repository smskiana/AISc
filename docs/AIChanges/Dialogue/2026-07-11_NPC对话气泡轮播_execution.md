> 设计方案: [2026-07-11_NPC对话气泡轮播_plan.md](2026-07-11_NPC对话气泡轮播_plan.md)

# NPC对话气泡轮播 — 执行记录

## 完成时间

2026-07-11

## 本次目标

修复 AI 驱动的 NPC 对话中头顶气泡重叠的问题，把当前显示方式改成更符合“你一句我一句”的轮流播报。

## 实际改动清单

### 修改脚本

- `Assets/Scripts/Dialogue/NpcBubbleManager.cs`
- `Assets/Scripts/Core/GameManager.cs`

### 新建文档

- `docs/AIChanges/Dialogue/2026-07-11_NPC对话气泡轮播_plan.md`
- `docs/AIChanges/Dialogue/2026-07-11_NPC对话气泡轮播_execution.md`

## 关键实现

### 1. `NpcBubbleManager` 改为按对话双方共用队列

原先逻辑是：

- 每个 `npc_id` 自己维护一条队列

这会导致：

- `A -> B` 和 `B -> A` 分别在两个人头上同时冒泡

现在改为：

- 用 `npc_id + target_npc_id` 生成稳定 `conversationKey`
- `A -> B` 与 `B -> A` 会进入同一条会话队列
- 同一会话只允许串行推进

因此同一组 NPC 的对白会按轮次依次播放，而不是并发显示。

### 2. 播放新一句前先隐藏双方旧气泡

在真正显示当前发言前，会先隐藏：

- 说话方当前气泡
- 目标方当前气泡

这样上一句会先收掉，再出现下一句，视觉上更像轮流对话。

### 3. 玩家开启正式对话时，清掉该 NPC 的世界气泡

`GameManager` 新增 `OnDialogueStarted` 事件。

`NpcBubbleManager` 收到后会：

- 清空该 NPC 参与的所有气泡队列
- 隐藏该 NPC 相关的旧气泡

避免头顶气泡和立绘对话 UI 同时出现。

### 4. 玩家对话进行中，忽略相关 NPC 的新世界气泡

如果当前正和某 NPC 进行正式对话，则 `NpcBubbleManager` 会忽略这个 NPC 作为说话方或目标方的新 `NPC_BUBBLE` 消息，避免对话中再次冒出干扰性气泡。

## 验证方式

1. 使用 Unity MCP `validate_script` 校验：
   - `Assets/Scripts/Dialogue/NpcBubbleManager.cs`
   - `Assets/Scripts/Core/GameManager.cs`
2. 使用 Unity MCP `read_console` 检查最新 `error / warning`

## 验证结果

- `NpcBubbleManager.cs` 校验通过：0 error / 0 warning
- `GameManager.cs` 校验通过：0 error / 1 warning
- 该 warning 为静态分析给出的字符串拼接 GC 提示，不是编译错误
- Unity Console 当前未读到新增 `error / warning`

## 说明

当前实现是“按双人对话轮播”，不是“全场全局只留一个气泡”。

也就是说：

- 同一组 NPC 会严格轮流说话
- 不同无关 NPC 组合仍可各自并行显示

这样既解决重叠问题，也不会把全场气泡节奏拖得过慢。
