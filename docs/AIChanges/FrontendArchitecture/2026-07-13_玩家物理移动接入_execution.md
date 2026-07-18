> 设计方案: [2026-07-13_玩家物理移动接入_plan.md](2026-07-13_玩家物理移动接入_plan.md)

# 玩家物理移动接入 - 执行记录

## 完成时间

2026-07-13

## 本次目标

修复玩家 WASD 移动直接修改 `Transform`，导致不受 Unity 2D 碰撞系统控制的问题。

## 实际改动

| 文件 / 资产 | 改动 |
|------|------|
| `Assets/Scripts/Core/PlayerController.cs` | 新增 `RequireComponent(typeof(Rigidbody2D))`；输入采样保留在 `Update()`；实际移动改为 `FixedUpdate()` 中调用 `Rigidbody2D.MovePosition()` |
| `Assets/Scenes/Town_Main.scene` | 通过 Unity MCP 给当前 `player_dy` 场景实例补 `Rigidbody2D`，并把 `CapsuleCollider2D.usedByComposite` 设为 `false` |
| `Assets/Prefabs/Player/Player_Main.prefab` | 通过 Unity MCP Prefab Stage 给 Player Prefab 根节点补 `CapsuleCollider2D` 与 `Rigidbody2D`，默认 layer 设为 `player` |
| `docs/AIChanges/ChangeIndex.md` | 登记本次执行记录 |

## 关键实现

1. 玩家输入仍在 `Update()` 读取，避免输入漏帧。
2. 玩家位移统一在 `FixedUpdate()` 用 `Rigidbody2D.MovePosition()` 执行，让 Unity 2D 物理参与碰撞求解。
3. Rigidbody2D 配置为 `Dynamic`、`gravityScale = 0`、`freezeRotation = true`、`interpolation = Interpolate`、`collisionDetectionMode = Continuous`。
4. 场景实例与 Prefab 同步补齐物理组件，避免只修当前场景、不修复后续实例化来源。

## 验证

1. Unity MCP 读取当前 `player_dy` 组件，确认包含 `PlayerController`、`CapsuleCollider2D`、`Rigidbody2D`。
2. Unity MCP 读取 Prefab Stage 根节点组件，确认包含 `PlayerController`、`CapsuleCollider2D`、`Rigidbody2D`。
3. 已保存 `Assets/Scenes/Town_Main.scene` 与 `Assets/Prefabs/Player/Player_Main.prefab`。
4. Unity Console 最终复查 error / warning 数量为 0。
5. 中途曾看到既有 `Assets/Scripts/Core/GameManager.cs(15,37)` 的 `_serverUrl` 未使用 warning，刷新后未再出现在最终复查结果中。

## 未完成项

1. 尚未做 Play 模式肉眼验证玩家撞墙手感。
2. 若后续仍能穿墙，应继续检查障碍物 Collider2D 是否为 Trigger、player 层是否被 Physics2D Layer Collision Matrix 排除。
