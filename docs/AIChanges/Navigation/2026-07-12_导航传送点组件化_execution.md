> 设计方案: [2026-07-12_导航传送点组件化_plan.md](2026-07-12_导航传送点组件化_plan.md)

# 导航传送点组件化执行记录

## 实际改动清单

### 问题澄清

用户指出“为什么没有传送点组件”。上一轮所谓“传送点自己决定容差”实际只把权力从 `AStarMovementProvider` 挪到了 `NavigationGridAsset.NavigationTeleportLink` 数据行，不是场景传送点组件。这个边界不够对。

本轮已改为：

1. 场景 `NavigationTeleportPoint` 是 authoring 权威。
2. `NavigationGridAsset` 只保存从组件同步来的运行时副本。
3. `AStarPathfinder` 只读取资产副本。
4. `AStarMovementProvider` 只执行 typed path。

### 新增组件

1. 新增 `Assets/Scripts/Navigation/NavigationTeleportPoint.cs`。
2. 组件字段包括：
   - `_id`
   - `_enabled`
   - `_exportsLink`
   - `_pairedPoint`
   - `_bidirectional`
   - `_triggerRadius`
   - `_entranceMatchRadius`
   - `_exitMatchRadius`
   - `_cost`
3. `TryBuildLink()` 会把场景组件导出为 `NavigationTeleportLink`。
4. `OnDrawGizmosSelected()` 显示触发半径和配对连线。

### 导航资产写入入口

1. 修改 `Assets/Scripts/Navigation/NavigationGridAsset.cs`。
2. 新增 `SetTeleportLinks(IReadOnlyList<NavigationTeleportLink>)`。
3. `NavigationTeleportLink` 新增无参构造和 `Create(...)` 工厂方法，供场景组件导出运行时副本。

### 烘焙器同步传送组件

1. 修改 `Assets/Scripts/Navigation/NavigationGridSpriteBaker.cs`。
2. 新增传送点配置：
   - `_teleportPointsRoot`
   - `_teleportPoints`
   - `_syncTeleportLinksAfterBake`
3. 新增按钮 / 菜单：
   - `CollectTeleportPointsFromRoot()`
   - `SyncTeleportLinksToAsset()`
4. `BakeToAsset()` 在配置了传送点来源时，会自动同步传送 links。
5. 完全未配置传送点 Root / 列表时，不会清空旧资产 links，避免误删现有配置。

### 场景资产配置

1. 使用 Unity MCP 给 `go_tranport_st` 下 8 对端点挂了 `NavigationTeleportPoint`。
2. 每对传送点：
   - 街道端 `_exportsLink=true`
   - 目标端 `_exportsLink=false`，只作为配对目标
   - `_bidirectional=true`
   - `_triggerRadius=0.35`
   - `_cost=1.0`
3. `nav_mapBake_st.NavigationGridSpriteBaker._teleportPointsRoot` 已指向 `go_tranport_st`。
4. 已调用 `SyncTeleportLinksToAsset()` 同步 `NavGrid_Main.asset`。
5. 已保存 `Town_Main.scene` 与资产。

同步后的 8 条 link：

1. `street_cafe`
2. `street_bookstore`
3. `street_park`
4. `street_bridge`
5. `street_police_box`
6. `street_wagashi`
7. `street_flower_shop`
8. `street_bakery`

### 工程索引

1. 更新 `Assets/Scripts/Index.md`。
2. 为命令行编译验证，将 `NavigationTeleportPoint.cs` 加入当前 `Assembly-CSharp.csproj`。

## 验证方式

1. `dotnet build AISc.sln --no-restore` 通过：
   - 0 error
   - 8 warning，均为既有 Unity 引用冲突 / JSON 字段未赋值 / `GameManager._serverUrl` 未使用 warning。
2. Unity MCP 刷新脚本后 Console：
   - 0 error
   - 既有 `GameManager._serverUrl` warning
   - MCP WebSocket warning
3. Unity MCP 查找 `NavigationTeleportPoint`：
   - 共 16 个组件，对应 8 对传送端点。
4. 抽查 `street_cafe`：
   - `go_streetCafe_st/street_st`：`ExportsLink=true`，paired 到 `cafe_st`
   - `go_streetCafe_st/cafe_st`：`ExportsLink=false`，paired 到 `street_st`
5. 直接读取 `NavGrid_Main.asset`：
   - `teleportLinks=8`
   - ID 与上方 8 条一致。
6. Unity MCP `validate_script`：
   - `NavigationTeleportPoint.cs` 通过：0 error / 0 warning
   - `NavigationGridSpriteBaker.cs` 通过 Unity / dotnet 编译，但 MCP 单文件校验器误报 `BuildEstimatedGridSizeText` 重复签名；源码与编译均无重复方法错误。

## 未完成项

1. 尚未 Play 模式观察 typed `TELEPORT link=...` 日志。
2. 当前双向 link 的两个方向共用同一套半径；如后续需要入口和出口方向分别不同，可扩展 `NavigationTeleportLink` 为双向独立半径。
