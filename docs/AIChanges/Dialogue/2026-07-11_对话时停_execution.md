> 设计方案: [2026-07-11_对话时停_plan.md](2026-07-11_对话时停_plan.md)

# 对话时停 — 执行记录

## 完成时间

2026-07-11

## 本次完成内容

已把“玩家与 NPC 对话”改成真正的时停状态。

现在对话期间会同时发生两件事：

1. 后端游戏时钟暂停，不再推进分钟，也不会继续跑 NPC 行为 tick
2. 前端若有 NPC 正在移动，会在画面上冻结，直到对话结束后再继续

因此这次不再是“只锁玩家”，而是更接近真正的世界暂停。

## 实际改动清单

### 修改脚本 (3)

- `backend/src/world/clock.py`
- `backend/src/application/dialogue_service.py`
- `Assets/Scripts/NPC/IMovementProvider.cs`

### 新建文档 (2)

- `docs/AIChanges/Dialogue/2026-07-11_对话时停_plan.md`
- `docs/AIChanges/Dialogue/2026-07-11_对话时停_execution.md`

## 关键实现说明

### 1. `GameClock` 新增真正的暂停机制

在 `clock.py` 中新增了：

1. `_pause_reasons`
2. `is_paused`
3. `push_pause(reason)`
4. `pop_pause(reason)`

时钟主循环现在在暂停期间不会继续累计现实时间，也不会推进游戏分钟。

这意味着：

1. 时间不会偷偷往前走
2. 依赖分钟推进的 `BehaviorEngine.tick()` 也不会继续触发

### 2. 玩家对话接入停表生命周期

在 `PlayerDialogueService` 中：

1. `start_dialogue()` 成功建立活跃对话后立即 `push_pause`
2. `end_dialogue()` 收尾时 `pop_pause`
3. 若首句 LLM 调用失败，会先释放 pause，再补发 `DIALOGUE_CLOSE`

这次顺手修掉了一个对话异常路径问题：

1. 以前如果开场生成失败，前端可能一直停留在对话态
2. 现在会明确关闭对话并恢复时钟

### 3. 前端正在进行中的 NPC 移动会被冻结

在 `LerpMovementProvider.MoveRoutine()` 中新增了：

1. 检查 `GameManager.Instance.IsDialogueActive`
2. 对话进行中时只 `yield return null`
3. 不累计 `elapsed`

这样若玩家开聊时某个 NPC 正走到一半：

1. 画面里会停在当前位置
2. 对话结束后继续沿原路径走完

## 验证结果

- [x] `backend/src/world/clock.py` 通过 `python -m py_compile`
- [x] `backend/src/application/dialogue_service.py` 通过 `python -m py_compile`
- [x] 对话开始 / 结束已接入时钟暂停与恢复
- [x] 前端移动协程已接入对话冻结判断

## 未完成项

1. 还没有在 Unity Play 模式中实际验证“NPC 走到一半时开聊，会不会真的停在半路”
2. 这轮只冻结了 NPC 活动主链与移动表现，没有额外冻结所有可能的 UI/气泡计时
3. `TimeSpeed.DIALOGUE` 目前仍保留在枚举中，但这轮的实际时停已不再依赖它

## 说明

1. 本次没有扩协议，也没有新增消息类型
2. 这轮优先解决的是“时间推进”和“NPC 行为/移动继续跑”的主问题
3. 由于当前项目里的 NPC 活动表现主要就是后端行为驱动 + 前端 Lerp 移动，因此这次修改已经能覆盖用户要求的核心效果
