# 快捷回复加载态修正 — 执行记录

## 完成时间

2026-07-11

## 问题现象

玩家进入下一轮对话后，快捷回复区会继续显示上一轮内容，不能稳定进入 `快捷回复生成中.` / `..` / `...` 的加载态。

## 根本原因

1. 后端 `dialogue_service.py` 在 `DIALOGUE_COMPLETE` 中立刻塞入了 fallback `choices`
2. 前端收到非空 `choices` 后会直接渲染按钮，因此不会进入快捷回复加载态
3. 旧按钮销毁使用 `Destroy()`，在当前帧结束前仍可能短暂可见，造成“上一轮内容还在”的观感

## 实际改动

### 修改文件

- `backend/src/application/dialogue_service.py`
- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`

### 修正内容

1. `DIALOGUE_COMPLETE` 现在统一发送空 `choices`
2. 快捷回复统一等待后续异步 `DIALOGUE_CHOICES_UPDATE` 再填充
3. `ClearChoiceButtons()` 在销毁旧按钮前，先把按钮 `SetActive(false)`，避免旧内容在这一帧继续可见

## 验证结果

- `dialogue_service.py` 已通过 `python -m py_compile`
- `PortraitDialogueUI.cs` 已通过 Unity MCP `validate_script`
- Unity Console 当前未读到新增 `error / warning`

## 当前效果

现在每一轮 NPC 回复结束后：

1. 先稳定进入 `快捷回复生成中.` / `..` / `...`
2. 再由 `DIALOGUE_CHOICES_UPDATE` 替换成这一次真正的新快捷回复
3. 不会再把上一轮选项残留在这一轮里
