# 传送入口触发偏宽记录执行记录

## Workstream

Navigation

## Roadmap item

NAV

## 相关 ADR

1. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`

## 记录内容

已记录低优先级已知问题：传送稳定但入口触发偏宽。

当前现象：

1. 传送链路整体稳定。
2. 入口触发范围偏宽，可能在靠近入口但尚未严格贴近触发点时被判定进入传送。

当前处理口径：

1. 暂时搁置，不进入当前修复排期。
2. 不回退 typed path。
3. 不重新引入 `AStarMovementProvider` 坐标反推传送。
4. 后续若影响玩家传送或 NPC 行为观感，再从 `NavigationTeleportPoint` / `NavigationTeleportLink` 的入口匹配半径与场景端点配置入手收窄。

## 实际改动清单

1. 更新 `docs/Workstreams/Navigation/README.md`，新增低优先级已知问题。
2. 更新 `docs/AIChanges/ChangeIndex.md`，在导航系统分组登记本记录。

## 验证方式

1. 静态检查导航工作流已出现“传送稳定但入口触发偏宽”记录。
2. 静态检查 ChangeIndex 已登记本执行记录。

本轮只记录问题，不修改代码，不运行编译。

## 未完成项

1. 未修复入口触发偏宽。
2. 未调整任何传送点半径或场景资产配置。
