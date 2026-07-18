> 设计方案: [2026-07-12_SceneAnchor区域采样与可达点_plan.md](2026-07-12_SceneAnchor区域采样与可达点_plan.md)

# SceneAnchor 区域采样与可达点执行记录

## 实际改动清单

### SceneAnchor 区域组合

1. `Assets/Scripts/Data/SceneAnchor.cs`
   - 新增 `SceneAnchorArea` 与 `SceneAnchorAreaShape`。
   - 支持圆形区域、矩形区域和多个区域组合。
   - 支持按区域权重随机采样。
   - 新增 `SampleCandidatePoints()`，给 A* 生成多个目标候选点。
   - 新增 `DistanceTo()`，让最近 location 反查按区域边界计算距离。
   - Gizmos 会绘制 Anchor 中心、圆形区域和矩形区域。
   - 增加 Odin Inspector 分组、列表抽屉、形状切换和条件字段显示。

2. `Assets/Scripts/Data/SceneAnchorRegistry.cs`
   - `GetPositionWithOffset()` 改为从 Anchor 区域采样。
   - 新增 `GetCandidatePositions()`，暴露多个候选落点。
   - 最近 Anchor 反查改用 `SceneAnchor.DistanceTo()`。

3. `Assets/Scripts/Data/LocationDatabase.cs`
   - `GetPositionWithOffset()` 优先使用 SceneAnchor 区域采样。
   - 新增 `GetCandidatePositions()`。
   - JSON fallback 保持旧圆形随机偏移，并能生成多个候选点。

### NPC 可达目标接入

1. `Assets/Scripts/NPC/IMovementProvider.cs`
   - 接口新增 `MoveToLocation()`。
   - `LerpMovementProvider` 实现 location 版本，仍按旧逻辑取一个随机落点后直线移动。

2. `Assets/Scripts/NPC/NpcEntity.cs`
   - `MoveToLocation()` 不再提前把 `locationId` 转成单个随机点。
   - 改为把 `locationId` 交给 `IMovementProvider.MoveToLocation()`，让 A* provider 可以自行筛选可达候选。
   - `TeleportTo()` 保持使用 Anchor 中心点，避免读档 / 刷新时随机跳动。

3. `Assets/Scripts/Navigation/AStarMovementProvider.cs`
   - 新增 location 移动入口。
   - 从 `LocationDatabase.GetCandidatePositions()` 获取 16 个候选点。
   - 每个候选点会先修正到最近可走格中心，再执行 A*。
   - 找到第一条可达路径后沿 waypoint 移动。
   - 若导航网格未配置，仍回退直线移动。
   - 若导航网格存在但所有候选点都不可达，则取消本次移动并输出 warning，避免 NPC 穿墙走到不可达点。

### 索引同步

1. `Assets/Scripts/Index.md`
   - 更新 `SceneAnchor`、`SceneAnchorRegistry`、`LocationDatabase`、`AStarMovementProvider` 说明。

## 遇到的问题

1. 本轮没有可用 Unity MCP 工具，因此只完成脚本层能力和命令行编译验证，未在编辑器资产层创建 / 连线实际 Anchor 区域。
2. 当前工作树整体处于未跟踪状态，`git diff` 不适合用于回看本轮差异；已通过文件内容和编译结果确认落盘。

## 验证方式

1. 执行 `dotnet build AISc.sln --no-restore`。
2. 结果：
   - 0 error。
   - 8 warning，均为既有 Unity 引用冲突、`LocationDatabase` JSON 字段未赋值、`GameManager._serverUrl` 未使用 warning。

## 未完成项

1. 尚未在 Unity 编辑器中给各个 `SceneAnchor` 配置圆形 / 方形区域。
2. 尚未通过 Unity MCP 或编辑器把实际导航网格资产挂到 `NpcSpawner`。
3. 尚未 Play 模式观察 NPC 在区域候选点之间的实际路径选择。
