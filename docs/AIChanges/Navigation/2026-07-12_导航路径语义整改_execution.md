> 设计方案: [2026-07-12_前端职责框架整改_plan.md](../FrontendArchitecture/2026-07-12_前端职责框架整改_plan.md)

# 导航路径语义整改执行记录

## 执行目标

本轮先整改导航第一阶段职责边界：

1. A* 输出保留 `Walk` / `Teleport` 语义的 typed path。
2. `NavigationTeleportLink` 自己决定入口 / 出口匹配半径。
3. `AStarMovementProvider` 只执行 typed path，不再靠坐标反推传送段。
4. 导航日志集中到独立工具类，降低移动执行类负担。

## 实际改动清单

### typed path 数据结构

1. 新增 `Assets/Scripts/Navigation/NavigationPath.cs`。
2. 新增 `NavigationPathSegmentType`：
   - `Walk`
   - `Teleport`
3. 新增 `NavigationPathSegment`，普通行走段保存 `FromWorld` / `ToWorld`，传送段保存：
   - `LinkId`
   - `EntranceWorld`
   - `ExitWorld`
   - `ResolvedExitWorld`
   - `IsReverse`
4. 新增 `NavigationPath`，作为 A* 的语义路径输出；旧 waypoint 接口通过 `AppendWaypoints()` 兼容。

### 传送点职责回收

1. 修改 `Assets/Scripts/Navigation/NavigationGridAsset.cs`。
2. `NavigationTeleportLink` 新增 Inspector 字段：
   - `_entranceMatchRadius`
   - `_exitMatchRadius`
3. `NavigationTeleportLink` 新增方法：
   - `GetEntranceMatchRadius(float cellSize)`
   - `GetExitMatchRadius(float cellSize)`
4. `CollectTeleportExits()` 使用 link 自己的入口匹配半径判断当前格是否能触发传送。
5. 出口吸附后会用 link 自己的出口匹配半径校验解析后的可走格，避免出口被吸附到离配置点过远的位置。
6. `NavigationTeleportExit` 扩展为带语义的传送边数据：
   - `LinkId`
   - `EntranceWorld`
   - `ExitWorld`
   - `ResolvedExitCell`
   - `ResolvedExitWorld`
   - `IsReverse`
7. `CollectTeleportExits()` 现在把单向 / 反向传送边的语义一并交给 A*，不再只返回一个出口 cell。

### A* 回溯保留传送语义

1. 重写 `Assets/Scripts/Navigation/AStarPathfinder.cs` 的路径输出链路。
2. `NodeRecord` 新增：
   - `CameFromIsTeleport`
   - `CameFromTeleport`
3. 普通邻居和传送邻居分别通过 `TryRelaxWalkNeighbor()` / `TryRelaxTeleportNeighbor()` 进入统一 relax。
4. 新增 `TryFindNavigationPath()`，输出 `NavigationPath`。
5. 旧 `TryFindPath()` 保留，内部调用 typed path 后展平成 waypoint，兼容已有调试工具。
6. 共线简化只应用在连续 walk run 上；遇到 teleport 会截断 walk run 并插入 `Teleport` segment，避免传送边界被简化吞掉。

### 移动执行层减重

1. 重写 `Assets/Scripts/Navigation/AStarMovementProvider.cs` 的路径执行部分。
2. `MoveTo()` / `MoveToLocation()` 改为请求 `TryFindNavigationPath()`。
3. `MoveAlongPath()` 现在按 `NavigationPathSegment` 顺序执行：
   - `Walk`：匀速移动到 `ToWorld`
   - `Teleport`：直接放置到 `ResolvedExitWorld`
4. 删除旧坐标反推逻辑：
   - `IsTeleportSegment()`
   - `MatchesTeleportDirection()`
5. location 候选点筛选和起点吸附仍暂留在本类，属于第二阶段再拆的 planner 职责。

### 导航日志集中

1. 新增 `Assets/Scripts/Navigation/NavigationDebugLog.cs`。
2. 集中输出：
   - `[AStarMove:npc/name]` 前缀
   - typed path 摘要
   - `TELEPORT link=...`
   - 长路径段
   - 移动完成位置
3. `AStarMovementProvider` 不再自己拼路径摘要和传送匹配日志。

### 工程索引

1. 更新 `Assets/Scripts/Index.md`。
2. 为命令行编译验证，将新脚本加入 `Assembly-CSharp.csproj` 的 `Compile Include` 列表；该文件仍是 Unity 生成文件，后续 Unity 重生项目文件时可能被覆盖。

## 验证方式

1. 搜索确认旧反推逻辑已移除：
   - `MatchesTeleportDirection`
   - `IsTeleportSegment`
2. 执行 `dotnet build AISc.sln --no-restore`：
   - 0 error
   - 8 warning，仍为既有 Unity 引用冲突 / JSON 字段未赋值 / `GameManager._serverUrl` 未使用 warning。
3. Unity MCP 强制刷新脚本：
   - `refresh_unity(scope=scripts/all, compile=request, wait_for_ready=true)`
4. Unity Console：
   - 0 error
   - 2 warning：既有 `GameManager._serverUrl` 未使用字段 warning 与 MCP WebSocket warning。
5. Unity MCP `validate_script`：
   - `AStarPathfinder.cs`：0 error / 0 warning
   - `AStarMovementProvider.cs`：0 error / 0 warning
   - `NavigationPath.cs`：0 error / 0 warning
   - `NavigationDebugLog.cs`：0 error / 0 warning
   - `NavigationGridAsset.cs`：Unity / dotnet 编译通过，但 MCP 单文件校验器误报 `GetBakedWalkableCellCount` 重复签名；源码搜索确认只有一个实现。

## 未完成项

1. 尚未做 Play 模式长跑验证，需要观察日志中是否出现：
   - `TELEPORT link=street_flower_shop`
   - `TELEPORT link=street_bakery`
   - `TELEPORT link=street_police_box`
2. 本轮未拆 `MoveToLocation()` 的候选点 planner。
3. 本轮未改 `NpcEntity.CurrentLocation` 的成功 / 失败语义。
4. 本轮未拆 `NpcBubbleManager` 的社交会合逻辑。
