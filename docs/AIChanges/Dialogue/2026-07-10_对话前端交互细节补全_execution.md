> 设计方案: [2026-07-10_对话前端交互细节补全_plan.md](2026-07-10_对话前端交互细节补全_plan.md)

# 对话前端交互细节补全 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已补齐玩家与 NPC 对话前端的三项关键交互细节：

1. NPC 说完一句后，前端会出现可输入的玩家回复框
2. 对话进行中会锁住玩家移动与再次点 NPC
3. 玩家发出下一句后，会先清空上一轮 NPC 台词，再展示新一轮回复

本次未改动后端协议，继续复用现有 `PLAYER_CHOICE` 文本输入通道。

## 实际改动清单

### 修改脚本 (3)

- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`
- `Assets/Scripts/Core/GameManager.cs`
- `Assets/Scripts/Core/PlayerController.cs`

### 新建文档 (2)

- `docs/AIChanges/Dialogue/2026-07-10_对话前端交互细节补全_plan.md`
- `docs/AIChanges/Dialogue/2026-07-10_对话前端交互细节补全_execution.md`

## 关键实现说明

### 1. `PortraitDialogueUI` 补自由输入区

新增回复相关字段与运行时兜底创建逻辑：

- `_replyPanel`
- `_replyInputField`
- `_sendButton`
- `_endDialogueButton`

如果当前场景里没有这些 UI 物体，`PortraitDialogueUI` 会在运行时自动创建：

- 输入提示
- `TMP_InputField`
- `发送` 按钮
- `结束对话` 按钮
- 缺失时自动补 `EventSystem`

因此这次修复不依赖你手工重搭 `DialogueCanvas`。

### 2. NPC 说完后统一开放回复

`GameManager` 的 `OnDialogueComplete` 由原来的“只有 `choices` 非空才处理”改为统一调用：

- `PortraitDialogueUI.OnNpcReplyComplete(msg.choices)`

这样即使后端没有返回选项列表，玩家也仍能通过文本输入继续对话。

### 3. 发送前清空上一轮 NPC 台词

在 `PortraitDialogueUI.SubmitReply()` 中，发送玩家回复前会统一执行：

- 隐藏选项区
- 隐藏输入区
- 清空输入框
- 清空 `_dialogueText`
- 清空 `_accumulatedText`
- 重置打字机状态

这样下一轮 `DIALOGUE_TOKEN` 会从空白文本开始，不再把上一轮内容接在后面。

### 4. 对话中锁玩家移动

`GameManager` 新增：

- `IsDialogueActive`
- `CurrentDialogueNpcId`

`PlayerController.Update()` 会在 `IsDialogueActive == true` 时：

- 不处理 `WASD / 方向键`
- 不处理点击 NPC
- 角色颜色恢复为 idle 状态

### 5. 提供结束对话出口

新增两种结束方式：

- 点击 `结束对话` 按钮
- 按 `Esc`

两者都会调用 `GameManager.EndDialogue()`：

- 本地先关闭 UI
- 本地先恢复玩家交互
- 再通知后端发送 `DIALOGUE_END`

后端回包 `DIALOGUE_CLOSE` 时也会走同一套本地收口逻辑。

## 验证结果

### 脚本 / 编译

- [x] Unity 脚本已刷新
- [x] 当前 Unity Console 无新增编译错误

### 功能层确认

- [x] `DialogueComplete` 不再依赖 `choices` 才开放回复
- [x] 对话中会锁住 `PlayerController` 的移动和再次点击
- [x] 玩家发送下一句前会清空上一轮 NPC 文本
- [x] 前端现在具备输入框、发送按钮、结束按钮、`Esc` 退出

## 说明

### 关于场景改动

本次没有强制修改 `SampleScene.scene` 或手工重建 `DialogueCanvas`，而是优先通过运行时补建 UI 的方式让现有场景直接生效。

### 关于后端协议

后端 `dialogue_service.py` 已经支持任意 `choice_text` 文本，因此本次不需要扩消息结构；前端只是把原先“只能等 choices”改成了“可自由输入”。

## 未完成项

1. 还没有把玩家自己发出的台词显示在 UI 中
2. 还没有加入“发送中”状态或防止重复提交的明确 loading 表现
3. 后端异常分支若只发 `DIALOGUE_TOKEN(is_complete=true)` 而不发 `DIALOGUE_COMPLETE`，输入区开放体验仍不是最优
