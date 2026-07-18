> 设计方案: [2026-07-12_NPC精灵烘焙导航成本场_plan.md](2026-07-12_NPC精灵烘焙导航成本场_plan.md)

# NPC 精灵烘焙导航成本场执行记录

## 实际改动清单

### 导航资产扩展

1. `Assets/Scripts/Navigation/NavigationGridAsset.cs`
   - 新增 `NavigationGridSourceMode`，支持 `MaskSprite` 与 `BakedCells` 两种来源。
   - 新增烘焙数据字段：每格可走状态、每格通行成本、烘焙来源摘要。
   - 新增 `SetBakedGrid(...)`，供烘焙器写入导航资产。
   - 新增 `GetTraversalCost(...)`，供 A* 使用每格成本。
   - 调试纹理现在会根据成本把可走格从绿色渐变到暖色。

2. `Assets/Scripts/Navigation/AStarPathfinder.cs`
   - A* 的邻居松弛代价改为 `moveCost * GetTraversalCost(next)`。
   - 离障碍物更近的高成本格仍可走，但会被算法自然降权。

### Sprite 组合烘焙工具

1. `Assets/Scripts/Navigation/NavigationGridSpriteBaker.cs`
   - 新增场景组件，用于从 SpriteRenderer 组合烘焙导航资产。
   - 支持地图 SpriteRenderer root / 显式列表。
   - 支持障碍物 SpriteRenderer root / 显式列表。
   - 地图 Sprite bounds 内为导航候选区域。
   - 障碍物 Sprite bounds 内或 inflation 范围内不可走。
   - 障碍物外的 dangerRadius 范围内按距离写入通行成本。
   - Context Menu `Bake Navigation Grid From Sprites` 会写入目标 `NavigationGridAsset` 并在 Editor 下保存资产。

2. `Assets/Scripts/Navigation/NavigationGridSpriteBaker.cs.meta`
   - 新增 Unity meta，保持脚本 GUID 稳定。

### 索引与兼容

1. `Assets/Scripts/Index.md`
   - 更新 `NavigationGridAsset` 与 `AStarPathfinder` 描述。
   - 新增 `NavigationGridSpriteBaker` 索引。

2. `docs/AIChanges/Navigation/2026-07-12_NPC自研A星寻路_execution.md`
   - 修正未完成项，说明主流程已从手绘黑白遮罩改为 SpriteRenderer 组合烘焙。

## 遇到的问题

1. 当前第一版按 SpriteRenderer 的 world bounds 烘焙，不读取 Sprite alpha 形状。
2. 这让流程更简单，也避免重新回到“手画像素遮罩”的成本；但复杂异形障碍会被当作矩形处理。
3. 后续如果需要更精细，可以给 `NavigationGridSpriteBaker` 增加按 Sprite alpha 采样的可选模式。

## 验证方式

1. 执行 `dotnet build AISc.sln --no-restore`。
2. 结果：
   - 0 error。
   - 11 warning，均为既有 Unity 引用冲突 / JSON 字段未赋值 / `GameManager._serverUrl` 未使用 warning。

## 未完成项

1. 尚未通过 Unity MCP 创建实际 `NavigationGridAsset` 资产。
2. 尚未在场景中创建 `NavigationGridSpriteBaker` 节点并连线地图 / 障碍物 SpriteRenderer。
3. 尚未把烘焙后的导航资产挂到 `NpcSpawner._navigationGrid`。
4. 尚未 Play 模式验证 NPC 路径、成本场绕行效果和传送点表现。
