> 设计方案: [2026-07-10_玩家三条提示对话_plan.md](2026-07-10_玩家三条提示对话_plan.md)

# 玩家三条提示对话 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已完成“每轮 NPC 回复后提供 3 条玩家可点击提示，同时保留自由输入”的主链实现。

最终效果设计为：

1. NPC 每轮说完后，后端会在 `DIALOGUE_COMPLETE` 中返回 3 条 `choices`
2. Unity 前端继续显示可点击选项按钮
3. 输入框不会被取消，玩家仍可直接自由输入任意文本

## 实际改动清单

### 修改脚本 (3)

- `backend/src/application/dialogue_service.py`
- `backend/src/dialogue/prompt_builder.py`
- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`

### 新建文档 (2)

- `docs/AIChanges/Dialogue/2026-07-10_玩家三条提示对话_plan.md`
- `docs/AIChanges/Dialogue/2026-07-10_玩家三条提示对话_execution.md`

## 关键实现说明

### 1. 后端开始稳定回传 3 条建议回复

在 `PlayerDialogueService` 中新增了建议回复生成流程：

1. 对话首句 NPC 回复完成后生成
2. 玩家每次发送 `PLAYER_CHOICE` 后，下一轮 NPC 回复完成时再次生成
3. 将结果塞入：

`DIALOGUE_COMPLETE.choices`

这样前端现有 `msg.choices` 渲染链路可以直接复用。

### 2. PromptBuilder 接管建议回复提示词组装

`PromptBuilder` 新增了 `build_player_reply_suggestions(...)`，会基于：

1. 当前 NPC
2. 当前目标（玩家）
3. 最近几句对话
4. 当前时间与地点
5. NPC 刚说完的话

来组装“给玩家产出 3 条建议回复”的专用 prompt。

约束包括：

1. 只输出 JSON
2. 恰好 3 条
3. 风格区分为顺接 / 追问关心 / 轻松保留

### 3. 生成失败时自动降级，不影响自由输入

在 `dialogue_service.py` 中补了两层保险：

1. 若 LLM 生成建议失败，直接返回 3 条兜底回复
2. 若 LLM 只返回 1-2 条，也会自动和兜底建议合并补满到 3 条

因此不会再出现：

1. `choices` 为空导致没有按钮
2. `choices` 数量不足 3 条
3. 因建议生成异常而阻断正常对话

### 4. 前端提示文案明确保留自由输入

`PortraitDialogueUI` 没有重做结构，只补了一处体验提示：

1. 当存在建议按钮时，提示文案明确显示“可点选建议，也可自由输入”
2. 当没有建议按钮时，仍明确提示可以自由输入

这样玩家能直接理解：

1. 按钮只是提示
2. 输入框仍然是完整可用的主入口

## 验证结果

### 后端

- [x] `dialogue_service.py` 通过 `python -m py_compile`
- [x] `prompt_builder.py` 通过 `python -m py_compile`
- [x] 建议回复链路已接入两处 `DIALOGUE_COMPLETE`
- [x] 数量不足 3 条时会自动补满

### 前端代码层

- [x] `PortraitDialogueUI` 仍保留选项按钮和输入框并存逻辑
- [x] 回复提示文案已明确“可点选建议，也可自由输入”

## 未完成项

1. 还没有在 Unity Editor 中实际点击 NPC 跑一轮对话，验证 3 个按钮的真实显示效果
2. 还没有观察模型实际生成的建议回复质量，后续可能需要再微调 prompt
3. 当前玩家自己发出的台词仍未展示到对话框中，这不影响功能，但体验上还可以继续补

## 说明

1. 本次没有扩协议，没有新增消息类型
2. 前端原有自由输入功能被保留，新增的 3 条提示只是辅助入口，不会取代自由说话
