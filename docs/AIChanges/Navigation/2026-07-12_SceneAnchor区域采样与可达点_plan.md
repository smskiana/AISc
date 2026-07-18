> 执行记录: [2026-07-12_SceneAnchor区域采样与可达点_execution.md](2026-07-12_SceneAnchor区域采样与可达点_execution.md)

# SceneAnchor 区域采样与可达点方案

## 需求理解

当前 `SceneAnchor` 只提供一个 Transform 点和圆形随机偏移，不能表达店门、柜台前、街道段等“可站区域”。本轮需要：

1. `SceneAnchor` 支持方形区域。
2. `SceneAnchor` 支持圆形区域。
3. `SceneAnchor` 支持多个区域组合。
4. NPC 去某个 location 时，最终目标点要尽量保证 A* 可达。

## 方案思路

1. `SceneAnchor`
   - 保留旧 `RandomOffsetRadius` 作为兼容字段。
   - 新增区域列表，每个区域可选圆形或矩形。
   - 区域使用 Anchor 本地坐标偏移，随 Anchor Transform 移动。
   - 提供 `SamplePoint()` 和 `SamplePoints()`。
   - Gizmos 画出所有圆 / 方区域。

2. `SceneAnchorRegistry` / `LocationDatabase`
   - `GetPositionWithOffset()` 改为从 Anchor 区域采样。
   - 新增批量候选点接口，供 A* provider 尝试多个目标点。
   - fallback JSON 仍保留旧圆形随机偏移。

3. `AStarMovementProvider`
   - 对目标 location 使用候选点列表尝试 A*。
   - 若候选点不可达，继续尝试下一个候选点。
   - 若所有候选都失败，回退原始目标点的路径检查；再失败时保留旧直线 fallback。

4. `IMovementProvider` / `NpcEntity`
   - 为移动接口新增可选 `MoveToLocation(...)`。
   - 默认实现仍转为单点 `MoveTo(...)`，避免影响非 A* provider。
   - `NpcEntity.MoveToLocation()` 调用 provider 的 location 版本，让 A* 能拿到 locationId 和候选点。

## 涉及文件

修改：

1. `Assets/Scripts/Data/SceneAnchor.cs`
2. `Assets/Scripts/Data/SceneAnchorRegistry.cs`
3. `Assets/Scripts/Data/LocationDatabase.cs`
4. `Assets/Scripts/NPC/IMovementProvider.cs`
5. `Assets/Scripts/NPC/NpcEntity.cs`
6. `Assets/Scripts/Navigation/AStarMovementProvider.cs`
7. `Assets/Scripts/Index.md`

## 风险点

1. C# 接口新增方法会影响所有实现；采用默认接口方法，当前 Unity C# 版本已支持。
2. 第一版区域组合按“任一区域可采样”处理，不做差集 / 排除区。
3. 可达保证依赖 A* provider；直线移动 provider 仍只使用采样点，不做可达性判断。
