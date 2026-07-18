> 设计方案: [2026-07-11_NPC名字牌行为后缀_plan.md](2026-07-11_NPC名字牌行为后缀_plan.md)

# NPC名字牌行为后缀 — 执行记录

## 完成时间

2026-07-11

## 本次目标

为 NPC prefab 内的 `txt_nameplate_dy` 名字牌补充行为后缀，让当前没有动作动画的计划执行也能被玩家快速识别。

## 实际改动清单

### 修改脚本

- `Assets/Scripts/NPC/NpcEntity.cs`
- `Assets/Scripts/NPC/NpcSpawner.cs`

### 新建文档

- `docs/AIChanges/NpcBehavior/2026-07-11_NPC名字牌行为后缀_plan.md`
- `docs/AIChanges/NpcBehavior/2026-07-11_NPC名字牌行为后缀_execution.md`

## 关键实现

### 1. `NpcEntity` 统一管理名字牌文本

新增名字牌刷新逻辑，把显示格式统一为：

- `NPC名`
- `NPC名（状态）`

当前已覆盖的主要状态包括：

- `（移动中）`
- `（工作中）`
- `（交流中）`
- `（休息中）`
- `（阅读中）`
- `（用餐中）`
- `（观察中）`
- `（待机中）`

未显式枚举到的动作会落到通用状态，避免再次出现“有行为但看不出是什么”的问题。

### 2. `PlayAction()` 切换动作时同步刷新名字牌

现在 NPC 每次收到后端下发的 `action_id` 时，不仅会更新颜色占位，也会同步更新名字牌后缀。

### 3. `NpcSpawner` 生成 NPC 时立即套用初始动作

新生成 NPC 后会立刻执行一次当前状态的 `PlayAction(state.current_action ?? "stand")`，因此不用等下一条行为广播，初始画面就能看到状态后缀。

## 验证方式

1. 使用 Unity MCP `validate_script` 校验：
   - `Assets/Scripts/NPC/NpcEntity.cs`
   - `Assets/Scripts/NPC/NpcSpawner.cs`
2. 使用 Unity MCP `read_console` 检查最新 `error / warning`
3. 检查脚本逻辑，确认 `Initialize()`、`PlayAction()`、新生成 NPC 的初始状态三处都能刷新名字牌

## 验证结果

- 已完成脚本修改
- `NpcEntity.cs` 校验通过：0 error / 0 warning
- `NpcSpawner.cs` 校验通过：0 error / 0 warning
- Unity Console 当前未读到新增 `error / warning`
- 尚未在真实 Play 模式下逐个观察所有动作文案的视觉体验

## 后续可选优化

1. 如果你后面想让文案更贴近策划表，可以把前端状态文案进一步细化成 `整理中`、`打扫中`、`看店中`
2. 如果后续补了动作动画，名字牌后缀可以保留为辅助信息，不必删除
