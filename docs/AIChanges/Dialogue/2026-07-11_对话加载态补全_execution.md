> 设计方案: [2026-07-11_对话加载态补全_plan.md](2026-07-11_对话加载态补全_plan.md)

# 对话加载态补全 — 执行记录

## 完成时间

2026-07-11

## 本次目标

为玩家与 NPC 的正式对话补齐等待阶段的前端反馈，让 AI 回复生成和快捷回复建议生成都不再表现为“空白卡住”。

## 实际改动清单

### 修改脚本

- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`
- `Assets/Scripts/Core/GameManager.cs`

### 新建文档

- `docs/AIChanges/Dialogue/2026-07-11_对话加载态补全_plan.md`
- `docs/AIChanges/Dialogue/2026-07-11_对话加载态补全_execution.md`

## 关键实现

### 1. `PortraitDialogueUI` 增加 NPC 回复加载态

新增了 NPC 回复等待状态：

- 开始对话后，先显示 `思考中.` / `思考中..` / `思考中...`
- 玩家提交下一句后，下一轮 NPC 回复到来前也会显示同样的动态加载态
- 收到首个 `DIALOGUE_TOKEN` 后，自动清掉加载文案并进入正常逐字机显示

这样玩家在等待首 token 的阶段不再看到空白框。

### 2. 快捷回复建议补占位按钮加载态

当 NPC 回复结束、但真实 `choices` 还没准备好时，前端会：

- 打开回复区
- 用现有 `ChoiceButton` 生成禁用态占位按钮
- 按 `快捷回复生成中.` / `..` / `...` 做动态轮播
- 同时提示“也可直接输入”

收到后续 `DIALOGUE_CHOICES_UPDATE` 后，会把占位按钮替换成真实建议回复。

### 3. `GameManager` 拆分两类消息入口

把原来都塞给 `OnNpcReplyComplete(...)` 的两条消息拆开了：

- `DIALOGUE_COMPLETE`：通知整轮 NPC 回复结束，并传入完整文本 + 当前 choices
- `DIALOGUE_CHOICES_UPDATE`：只更新快捷回复建议，不再重复走整轮回复结束逻辑

这样加载态、文本态、建议回复态的职责边界更清楚。

## 验证方式

1. 使用 Unity MCP `validate_script` 校验：
   - `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`
   - `Assets/Scripts/Core/GameManager.cs`
2. 使用 Unity MCP `read_console` 检查最近控制台输出

## 验证结果

- `PortraitDialogueUI.cs` 校验通过：0 error / 1 warning
- `GameManager.cs` 校验通过：0 error / 1 warning
- 这两个 warning 都是静态分析给出的字符串拼接 GC 提示，不是编译错误
- Unity Console 未见新增脚本报错
- 当前 Console 仍有既存 TMP 字体缺字 warning，属于字体资源覆盖范围问题，不是本轮加载态逻辑引入

## 说明

### 当前体验变化

现在玩家会看到两个明确等待阶段：

1. NPC 正在生成回复时：对话框点点点加载
2. 快捷回复建议正在生成时：选项区点点点加载

### 仍保留的原有能力

- 玩家依然可以自由输入，不会被快捷回复加载态锁住
- 后端如果立刻返回 fallback choices，前端会直接显示真实选项，加载态可能很短或不出现
