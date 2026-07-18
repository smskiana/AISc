> 设计方案: [2026-07-13_GameCommandSender拆分_plan.md](2026-07-13_GameCommandSender拆分_plan.md)

# GameCommandSender 拆分执行记录

## 实际改动

1. 新增 `Assets/Scripts/Core/GameCommandSender.cs`，统一构造并发送前端到后端的游戏命令。
2. 通过 Unity AssetDatabase 导入新脚本，生成 `Assets/Scripts/Core/GameCommandSender.cs.meta`。
3. 修改 `Assets/Scripts/Core/GameManager.cs`，保留原公开 API，由 facade 方法委托给 `GameCommandSender`。
4. 修改 `Assembly-CSharp.csproj`，补入 `GameCommandSender.cs` 编译项。
5. 更新 `Assets/Scripts/Index.md`，登记高频核心脚本入口。
6. 更新 `docs/AIChanges/ChangeIndex.md`，登记本次前端职责拆分记录。

## 行为边界

1. 本轮不改变 WebSocket 协议字段。
2. 本轮不改变开始游戏、对话、快进、移动、存档和读档的外部调用方法。
3. 本轮不继续处理 `GameStateStore`、`NpcBehaviorApplier`、`NpcSocialRendezvousController`。

## 验证方式

1. `rg "WS\.Send|EscapeJson|new GameCommandSender|_commandSender|JsonUtility.ToJson" Assets/Scripts/Core Assets/Scripts/Dialogue`
2. `dotnet build AISc.sln --no-restore`
3. Unity MCP 刷新脚本并校验 `Assets/Scripts/Core/GameCommandSender.cs` 与 `Assets/Scripts/Core/GameManager.cs`。

## 验证结果

1. `rg` 检查通过：当前只有 `Assets/Scripts/Core/GameCommandSender.cs` 直接调用 `_webSocketClient.Send(JsonUtility.ToJson(command))`；`GameManager` 只保留 facade 委托。
2. `dotnet build AISc.sln --no-restore` 通过：0 error，8 warning。warning 为既有程序集版本冲突、`LocationDatabase` JSON 字段未赋值、`GameManager._serverUrl` 未使用。
3. Unity MCP `validate_script`：
   - `Assets/Scripts/Core/GameCommandSender.cs`：0 warning，0 error。
   - `Assets/Scripts/Core/GameManager.cs`：0 error，保留 1 个既有 `Update()` 字符串拼接 GC warning。
4. Unity Console 清理旧日志并刷新后无脚本编译错误；仅出现一次 MCP WebSocket 重连 warning，非项目代码错误。

## 未完成项

按 Roadmap 顺序，后续继续拆：

1. `GameStateStore`
2. `NpcBehaviorApplier`
3. `NpcSocialRendezvousController`
