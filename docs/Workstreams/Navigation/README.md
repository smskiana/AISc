# 工作流：导航系统

## 当前目标

让 NPC 移动从“坐标点移动”收敛为“语义路径执行”：SceneAnchor 提供候选点，A* 输出 typed path，移动器只执行路径，不反推传送。

导航系统只回答“能不能到、怎么到、是否到达”。NPC 是否应该去某处、在那里做什么，归 `docs/Workstreams/NpcBehavior/README.md` 维护。

## 当前工程口径

1. `SceneAnchor` 表示地点可站区域，不再只是单点。
2. `NavigationGridAsset` 保存可走格、通行成本和从场景组件同步来的传送 link。
3. `NavigationTeleportPoint` 是传送点 authoring 组件。
4. `AStarPathfinder` 输出 `NavigationPath`，保留 `Walk` / `Teleport` 段语义。
5. `AStarMovementProvider` 执行 typed path，不再用坐标反猜传送段。
6. `NavigationDebugLog` 统一输出导航诊断。

## 已完成阶段

1. 自研 A* 第一版。
2. SpriteRenderer 组合烘焙导航成本场。
3. Odin 导航烘焙面板优化。
4. SceneAnchor 区域采样与 A* 可达点。
5. 导航传送点配置。
6. NPC 导航反直觉修正。
7. 导航路径语义整改。
8. 导航传送点组件化。
9. `IMovementProvider` 移动结果语义：成功、失败、取消。
10. `NpcEntity.CurrentLocation` 改为确认到达后更新。
11. 正式日程候选由 Unity 内部任务命令执行，终态只通过 `NPC_RUNTIME_EVENT` 非阻塞同步；旧网络 `NPC_BEHAVIOR / NPC_ACTION_RESULT` 无生产入口。
12. NPC 移动期间后端使用唯一 transit 位置，不属于出发地、目标地或任何其他地区。
13. 移动成功、失败、取消已接入行为 request/result 回报，旧 request 不会覆盖新状态。
14. 移动不再由 `walk_to` / `run_to` action 表达；任意正式任务在目标 spot 不同时通过 `movement_mode` 请求导航阶段。
15. 跨店、同地点、成功 / 失败 / 取消、旧结果乱序和 transit 的关键 Play 回归已完成。
16. 玩家传送 / 场景入口已接入：玩家靠近现有 `NavigationTeleportPoint` 显示“按 F 前往”，按 F 后移动到配对出口并立即同步 `location_id`。
17. 玩家侧按职责拆为 `PlayerTeleportController`、`PlayerLocationResolver`、`PlayerTransitionView`，未复用 NPC 自动寻路执行器。

## 下一阶段建议

1. 保持已完成的 typed path 和移动结果边界，不为 NPC 任务语义增加导航特例。
2. 拆出 location candidate planner。
3. 如后续新场景出现视觉空白移动，再评估 alpha 采样或显式可走区域烘焙。

## 玩家传送当前口径

1. 玩家传送已完成，不再属于夜间回家睡觉闭环之前的待办项。
2. 玩家不直接复用 NPC 自动寻路执行器，但复用同一套地点、`SceneAnchor` 和 `NavigationTeleportPoint` 语义。
3. 当前职责已拆为 `PlayerTeleportController`、`PlayerLocationResolver`、`PlayerTransitionView`。
4. 传送完成后立即更新玩家当前 location，为玩家事件、NPC 见闻和存档提供可靠地点。
5. 当前能力已在 `Town_Main` 落地；新增场景继续复用相同组件和 UI 入口，不复制另一套玩家传送数据。

## 已知问题

详见 `docs/KnownIssues.md` 的导航系统条目。

当前已登记：

1. `NAV-LOW-001`：传送稳定但入口触发偏宽，低优先级暂缓。

## 暂缓事项

1. 不再把传送容差写回 `AStarMovementProvider`。
2. 不做大规模重建场景 / Prefab。
3. 不把 bounds 烘焙立即升级为复杂 alpha 轮廓，除非 Play 验证证明必要。
4. 不把玩家传送逻辑塞进 `AStarMovementProvider`。
5. 不用随机可达点替代 NPC 行为语义。

## 相关设计与决策

1. `docs/DesignDocs/CodebaseBigPicture.md`
2. `docs/AIChanges/FrontendArchitecture/2026-07-12_前端职责框架整改_plan.md`
3. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`

## 相关执行证据

详见 `docs/AIChanges/Navigation/README.md`。
