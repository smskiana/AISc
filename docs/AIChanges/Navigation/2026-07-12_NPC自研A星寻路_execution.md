> 设计方案: [2026-07-12_NPC自研A星寻路_plan.md](2026-07-12_NPC自研A星寻路_plan.md)

# NPC 自研 A* 寻路执行记录

## 实际改动清单

### 新增导航系统

1. `Assets/Scripts/Navigation/NavigationGridAsset.cs`
   - 新增 2D 静态导航网格 ScriptableObject。
   - 支持从 Sprite 遮罩读取可走格。
   - 支持世界坐标 / 网格坐标转换。
   - 支持起终点附近最近可走格修正。
   - 支持传送点配置与调试纹理生成。

2. `Assets/Scripts/Navigation/AStarPathfinder.cs`
   - 新增纯 C# A* 搜索实现。
   - 支持 4 向 / 8 向移动。
   - 支持禁止斜向穿墙角。
   - 支持传送点作为额外邻接边。
   - 路径输出为世界坐标 waypoint。

3. `Assets/Scripts/Navigation/AStarMovementProvider.cs`
   - 新增 `IMovementProvider` 实现。
   - NPC 先查 A* 路径，再沿 waypoint 移动。
   - 保留对话 / 气泡移动锁暂停逻辑。
   - 网格未配置或路径失败时回退旧直线移动。

4. `Assets/Scripts/Navigation/NavigationGridOverlay.cs`
   - 新增场景调试覆盖图组件。
   - 可把导航网格渲染为半透明 Sprite。
   - 可走格、不走格、传送入口、传送出口使用不同颜色。

5. `Assets/Scripts/Navigation/NpcNavigationDebugController.cs`
   - 新增 Play 模式调试控制组件。
   - 支持通过热键或右键菜单控制指定 NPC 移动到目标 `location_id`。

### 接入现有 NPC 链路

1. `Assets/Scripts/NPC/NpcSpawner.cs`
   - 新增 `_useAStarNavigation` 与 `_navigationGrid` 配置。
   - 若启用且配置了导航网格，则使用 `AStarMovementProvider`。
   - 未配置时继续使用 `LerpMovementProvider`，避免破坏现有流程。

2. `Assets/Scripts/Index.md`
   - 新增 `Navigation` 索引入口。
   - 更新 `NpcSpawner` 说明，标注可接入 A* 导航。

3. `Assembly-CSharp.csproj`
   - 补入新增导航脚本的 `Compile Include`，用于当前命令行编译验证。
   - 备注：Unity 刷新项目文件后可能会重生成此文件。

4. `Assets/Scripts/Navigation*.meta`
   - 补齐新目录和新脚本的 Unity `.meta`，保持 GUID 稳定。

## 遇到的问题

1. `dotnet build AISc.sln --no-restore` 首次失败：
   - 原因：当前 `Assembly-CSharp.csproj` 显式列出脚本，新建目录脚本未自动进入编译项。
   - 处理：把 5 个新增导航脚本加入 `Compile Include` 后复编通过。

2. 回退直线移动的停止逻辑需要收口：
   - 原因：A* 失败后会启动旧 `LerpMovementProvider`，下一次 Stop 也应停止该回退协程。
   - 处理：`AStarMovementProvider.Stop()` 同步调用 `_fallbackMovement.Stop(transform)`。

## 验证方式

1. 执行 `dotnet build AISc.sln --no-restore`。
2. 结果：
   - 0 error。
   - 8 warning，均为既有 Unity 引用冲突 / `LocationDatabase` JSON 字段未赋值 / `GameManager._serverUrl` 未使用 warning。

## 未完成项

1. 尚未创建实际 `NavigationGridAsset` 资产。
2. 2026-07-12 后续已改为优先使用 SpriteRenderer 组合烘焙导航成本场，不再推荐手绘黑白导航遮罩作为主流程。
3. 尚未通过 Unity MCP 把导航资产挂到 `NpcSpawner`。
4. 尚未在 Play 模式观察 NPC 路径、传送点和调试覆盖图实际表现。
