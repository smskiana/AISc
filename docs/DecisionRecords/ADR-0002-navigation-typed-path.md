# ADR-0002: 导航系统保留 typed path 语义

## 状态

Accepted

## 背景

导航系统早期把 A* 输出展平成 `Vector2` waypoint。这样会丢失传送边语义，导致 `AStarMovementProvider` 只能用坐标反推“这段是不是传送”，容差和规则也被迫堆到移动执行层。

该问题已经导致过 NPC 虚空移动、传送段误判和职责膨胀。

## 决定

导航系统必须保留 typed path：

1. `AStarPathfinder` 输出 `NavigationPath`。
2. 路径段使用 `NavigationPathSegmentType.Walk` / `Teleport` 区分。
3. `Teleport` 段携带 link id、入口、出口和解析后的出口坐标。
4. `AStarMovementProvider` 只执行 typed path，不反推传送。
5. 传送点匹配半径和成本归 `NavigationTeleportPoint` / `NavigationTeleportLink` 管理。

## 放弃或暂缓

1. 不再使用移动器里的坐标反推传送。
2. 不继续向 `AStarMovementProvider` 增加传送特殊判断。
3. 暂不立刻升级为复杂 alpha 采样烘焙，除非 Play 验证证明 bounds 烘焙不够。

## 影响

1. 新导航功能应优先保持语义路径，而不是退回裸坐标列表。
2. 后续要拆移动结果、候选点 planner 和社交会合控制器。
3. 调试日志应从 typed path 输出路径摘要。

## 当前实现补充

社交会合控制器已拆分并进一步形成两层职责：`NpcSocialProtocolController` 管理协议终态，`NpcSocialRendezvousController` 管理距离和移动锁。候选点 planner 仍未拆分。本补充不改变 typed path 决策。

## 相关入口

1. `docs/Workstreams/Navigation/README.md`
2. `docs/DesignDocs/CodebaseBigPicture.md`
3. `docs/AIChanges/FrontendArchitecture/2026-07-12_前端职责框架整改_plan.md`
