> 设计方案: [2026-07-13_前端职责拆分类补齐_plan.md](2026-07-13_前端职责拆分类补齐_plan.md)

# 前端职责拆分类补齐执行记录

## 实际改动

1. 新增 `Assets/Scripts/Core/GameStateStore.cs`，集中写入 `GameManager` 暴露的游戏时间、NPC 缓存、玩家位置、睡眠、玩法就绪和正式对话状态。
2. 修改 `Assets/Scripts/Core/GameManager.cs`，保留公开属性、事件和对外方法，由 `_stateStore` 承担状态写入，由 `GameCommandSender` 承担命令发送。
3. 新增 `Assets/Scripts/NPC/NpcBehaviorApplier.cs`，从 `NpcSpawner` 拆出 NPC 行为消息应用逻辑。
4. 修改 `Assets/Scripts/NPC/NpcSpawner.cs`，保留 NPC 生成、查找和事件订阅，行为落地委托给 `NpcBehaviorApplier`。
5. 新增 `Assets/Scripts/Dialogue/NpcSocialRendezvousController.cs`，从 `NpcBubbleManager` 拆出 NPC-NPC 社交靠近、等待距离和移动锁管理。
6. 修改 `Assets/Scripts/Dialogue/NpcBubbleManager.cs`，保留气泡队列、轮播和正式对话清理，社交 rendezvous 委托给 `NpcSocialRendezvousController`。
7. 更新 `Assembly-CSharp.csproj`、`Assets/Scripts/Index.md`、`docs/AIChanges/ChangeIndex.md`。
8. 通过 Unity AssetDatabase 导入三个新脚本并生成对应 `.meta`。

## 行为边界

1. 不改变后端 WebSocket 协议字段。
2. 不改变现有 MonoBehaviour 挂载和 SerializeField 连线。
3. 不改变 `GameManager`、`NpcSpawner`、`NpcBubbleManager` 对外调用入口。

## 验证结果

1. `dotnet build AISc.sln --no-restore` 通过：0 error，8 warning。warning 为既有程序集版本冲突、`LocationDatabase` JSON 字段未赋值、`GameManager._serverUrl` 未使用。
2. Unity MCP `validate_script`：
   - `Assets/Scripts/Core/GameStateStore.cs`：0 warning，0 error。
   - `Assets/Scripts/Core/GameManager.cs`：0 error，保留 1 个既有 `Update()` 字符串拼接 GC warning。
   - `Assets/Scripts/NPC/NpcBehaviorApplier.cs`：0 warning，0 error。
   - `Assets/Scripts/NPC/NpcSpawner.cs`：0 warning，0 error。
   - `Assets/Scripts/Dialogue/NpcSocialRendezvousController.cs`：0 warning，0 error。
   - `Assets/Scripts/Dialogue/NpcBubbleManager.cs`：0 warning，0 error。
3. Unity Console 清理旧日志并刷新后无项目脚本编译错误；仅出现一次 MCP WebSocket 重连 warning，非项目代码错误。
4. `rg` 检查通过：旧的 `UpdateNpcState`、`ShouldWaitForNpcDialogueParticipants`、`MoveNpcToSocialLocation` 已从原类中移除或迁移到新职责类。

## 未完成项

本轮已完成用户指定的四个拆分类整改。后续可继续按 Roadmap 检查更细的 UI 框剪与 prefab/场景资产层治理。
