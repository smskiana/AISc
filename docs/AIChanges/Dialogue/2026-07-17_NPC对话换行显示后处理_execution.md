# NPC 对话换行显示后处理执行记录

> 设计方案：本次为单文件小修，未创建 plan。

## 需求理解

模型回复包含括号动作、对白和段落空行；Unity 正式对话框高度固定，直接显示原始换行会导致内容超出可视区域。目标是在显示层折叠显式换行，不改变后端原文和对话语义。

## 实际改动

1. 修改 `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`。
2. `AppendToken` 对流式累计文本执行 `FormatNpcReplyForDisplay`，避免生成中出现大量空行。
3. `OnNpcReplyComplete` 对最终回复执行同一处理，保证流式和最终显示一致。
4. 新增 `FormatNpcReplyForDisplay`：将 CRLF / LF / CR 折叠为单个空格，并去除首尾空白；括号动作、对白文字和标点均保留。

## 诊断钩子评估

本次只改变 Unity UI 的显示格式，不新增或改变业务状态、执行阶段、失败原因、请求关联 ID 或协议字段，因此不需要修改 `aisc_debug` / `aisc_control` DTO、provider 或 MCP action。

## 验证

- 已检查 `AppendToken` 与 `OnNpcReplyComplete` 均经过统一格式化入口。
- 已检查格式化逻辑同时覆盖 `\r\n`、`\n`、`\r`，并对连续换行只产生一个显示空格。
- 当前环境未运行 Unity Editor Play 模式，尚未完成截图级 UI 验收。

## 未完成项

需要在 Unity Play 模式用包含括号动作和多段空行的真实 LLM 回复确认 TMP 文本框不再被显式换行撑满；若视觉上仍超出，应优先调整对话框高度或字号，而不是恢复原始空行。
