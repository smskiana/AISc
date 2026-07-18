> 设计方案: [2026-07-12_NPC导航反直觉修正_plan.md](2026-07-12_NPC导航反直觉修正_plan.md)

# NPC 导航反直觉修正执行记录

> 历史状态提示：本文“收到 `NPC_SOCIAL_ACTION` 后移动、气泡自行等待靠近”的链路已被 `2026-07-14_NPC社交协议闭环_execution.md` 取代。当前默认链路先 PREPARE 会合，READY 后才生成气泡。

## 实际改动清单

### 传送边移动修正

1. `Assets/Scripts/Navigation/AStarMovementProvider.cs`
   - `MoveAlongPath()` 在逐段移动前识别当前路径段是否为导航传送 link。
   - 新增 `IsTeleportSegment()`。
   - 新增 `MatchesTeleportDirection()`。
   - 若路径段匹配传送入口 / 出口，则直接把 NPC 放到出口可走格中心，不再从入口直线穿过虚空走到出口。
   - `MoveToLocation()` 在寻路前调用 `SnapStartToNearestWalkable()`。
   - 若 NPC 当前位于不可走格，会先瞬移吸附到最近可走格中心，避免 A* 起点修正被播放成“从室内/空白区直线走到传送点”的虚空移动。
   - 新增 `[AStarMove:npc_id/name]` 导航诊断日志，输出移动请求、起点吸附、候选点命中、路径摘要、传送段执行、长路径段和移动完成位置。
   - 根据 Play 模式日志，千早曾出现 `from=(-1.162,0.749) to=(-11.462,-0.451) distance=10.37` 的非传送长段；该段终点贴近花店传送出口，但起点距街道入口约 `0.62`，超过旧 `0.50` 识别容差。
   - 传送入口识别容差从 `triggerRadius + cellSize * 1.5` 调整为 `triggerRadius + cellSize * 4`；仍要求 waypoint 靠近传送出口，避免普通长路径被误判为传送。
   - 日志开关从 `const` 改为 `static readonly`，避免命令行编译产生不可达代码 warning。

2. `Assets/Scripts/Navigation/AStarPathfinder.cs`
   - `SimplifyCollinearCells()` 保留非相邻图边的两端点。
   - 新增 `IsGraphJump()` 与 `AddCellIfDifferent()`。
   - 传送边在 A* cell path 中表现为跨格跳跃，路径简化时必须保留入口和出口，否则移动层可能识别不到传送段，又把入口到后续 waypoint 播放成直线移动。

### NPC-NPC 气泡对话靠近后再显示

1. `Assets/Scripts/Dialogue/NpcBubbleManager.cs`
   - 新增 NPC 对话物理距离参数：
     - `_maxNpcDialogueDistance = 2.2f`
     - `_npcDialogueWaitTimeoutSec = 12f`
     - `_npcDialogueRetryIntervalSec = 0.5f`
   - `HandleNpcSocialAction()` 收到 NPC 社交动作后，会让双方都 `MoveToLocation(msg.location_id)`。
   - 世界气泡显示前会检查双方 Transform 距离。
   - 如果双方距离过远，气泡会等待双方靠近；超时后跳过该气泡，避免隔着地图或店铺虚空交流。
   - 移动锁只在气泡真正显示时施加，避免提前锁住正在靠近的 NPC。

### 场景保存

1. `Assets/Scenes/Town_Main.scene`
   - Unity 脚本刷新后场景产生 dirty，已保存，确保 `NpcBubbleManager` 新增序列化字段进入场景。

## 验证方式

1. 执行 `dotnet build AISc.sln --no-restore`。
2. 结果：
   - 0 error。
   - 8 warning，仍为既有 Unity 引用冲突 / JSON 字段未赋值 / `GameManager._serverUrl` 未使用 warning。
3. 使用 Unity MCP `validate_script` 检查 `AStarPathfinder.cs`：
   - 0 error。
   - 0 warning。
4. 使用 Unity MCP `validate_script` 检查 `AStarMovementProvider.cs`：
   - 0 error。
   - 0 warning。
5. 使用 Unity MCP `refresh_unity` 触发 Unity 刷新。
6. 读取 Unity Console：
   - 0 error。
   - 2 warning：既有 `GameManager._serverUrl` 未使用字段 warning 与 Unity MCP WebSocket 重连 warning。
7. 保存 `Town_Main.scene`。
8. 曾短暂出现多条 `The referenced script (Unknown) on this Behaviour is missing!` 旧 Console 日志；已用编辑器只读脚本检查当前场景 missing script 数量为 0，清空并刷新后未复现。

## 仍需 Play 模式确认

1. NPC 从街道进入店铺时，应在传送 link 处瞬移，不再跨地图虚空直线移动。
2. NPC-NPC 对话应等双方靠近后再冒气泡。
3. 如果仍出现非传送段虚空行走，下一步优先检查导航烘焙资产：
   - 地图 Sprite bounds 是否把视觉空白也算成可走区域。
   - 障碍物 Sprite / air wall 是否覆盖了不该走的区域。
   - 是否需要从 bounds 烘焙升级到 alpha 采样或显式可走区域烘焙。
