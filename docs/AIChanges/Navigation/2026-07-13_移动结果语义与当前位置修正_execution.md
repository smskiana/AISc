> 设计方案: [2026-07-13_移动结果语义与当前位置修正_plan.md](2026-07-13_移动结果语义与当前位置修正_plan.md)

# 移动结果语义与当前位置修正执行记录

## 实际改动

1. 修改 `Assets/Scripts/NPC/IMovementProvider.cs`：
   - 新增 `MovementResult`：`Succeeded`、`Failed`、`Cancelled`。
   - 将 `MoveTo` / `MoveToLocation` 回调改为 `Action<MovementResult>`。
   - `LerpMovementProvider` 记录自身 coroutine 和回调，成功、失败、取消都只回调一次。
2. 修改 `Assets/Scripts/NPC/NpcEntity.cs`：
   - `MoveToLocation` 回调升级为 `Action<MovementResult>`。
   - 移动开始时不再提前写 `CurrentLocation`。
   - 只有移动结果为 `Succeeded` 时才写入目标 `locationId`。
3. 修改 `Assets/Scripts/Navigation/AStarMovementProvider.cs`：
   - 接入 `MovementResult`。
   - A* 路径执行成功返回 `Succeeded`。
   - Transform / runner 缺失、候选全部不可达返回 `Failed`。
   - `Stop(transform)` 取消正在执行的 A* 移动并返回 `Cancelled`。
4. 更新 `docs/Workstreams/Navigation/README.md`，将本轮两项从下一阶段建议移动到已完成阶段。

## 行为边界

1. 不改变 typed path / teleport path 语义。
2. 不新增传送容差或坐标反推逻辑。
3. 不改变 `NpcEntity.TeleportTo`，直接传送仍然会立即更新 `CurrentLocation`。

## 验证结果

1. `rg` 检查通过：旧的无参 `Action onComplete` / `onComplete?.Invoke()` 移动完成语义已清理。
2. `dotnet build AISc.sln --no-restore` 通过：0 error，8 warning。warning 为既有程序集版本冲突、`LocationDatabase` JSON 字段未赋值、`GameManager._serverUrl` 未使用。
3. Unity MCP `validate_script`：
   - `Assets/Scripts/NPC/IMovementProvider.cs`：0 warning，0 error。
   - `Assets/Scripts/NPC/NpcEntity.cs`：0 warning，0 error。
   - `Assets/Scripts/Navigation/AStarMovementProvider.cs`：0 warning，0 error。
4. Unity Console 刷新后无项目脚本错误；仅保留既有 `GameManager._serverUrl` 未使用 warning。

## 未完成项

仍需 Play 模式复验 NPC 跨店移动、不可达候选失败和移动中取消三类运行时表现。
