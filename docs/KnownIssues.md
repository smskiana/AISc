# 已知问题索引

## 作用

本文记录当前仍存在、暂缓处理或待进一步验证的问题。

本文不替代 `docs/DesignDocs/ErrorPreventionIndex.md`：

1. `KnownIssues.md` 记录“还没修 / 暂缓 / 待验证”的问题。
2. `ErrorPreventionIndex.md` 记录“已经修正、后续需要防复发”的低级错误。

## 使用规则

1. 新增已知问题时，写清系统、优先级、状态、现象、当前处理口径和后续触发条件。
2. 如果问题已经修复，应在对应执行记录中说明，并从本文移除或改为“已修复，见执行记录”。
3. 如果问题变成高优先级阻塞，应同步更新 `docs/Roadmap.md` 或对应 `docs/Workstreams/*/README.md`。
4. 不把原始日志、长篇调试过程或猜测堆在本文；细节进入对应 execution 或 artifacts。

## 问题列表

### NAV-LOW-001：传送稳定但入口触发偏宽

- 系统：导航系统
- 优先级：低
- 状态：暂缓，不进入当前修复排期
- 记录日期：2026-07-12
- 相关执行记录：`docs/AIChanges/Navigation/2026-07-12_传送入口触发偏宽记录_execution.md`
- 相关 ADR：`docs/DecisionRecords/ADR-0002-navigation-typed-path.md`

#### 现象

当前传送链路整体稳定，typed path 和传送段执行已收敛；但入口触发范围偏宽，可能在靠近入口但尚未严格贴近触发点时被判定进入传送。

#### 当前处理口径

1. 暂时搁置，不进入当前修复排期。
2. 不因该问题回退 typed path。
3. 不重新引入 `AStarMovementProvider` 坐标反推传送。

#### 后续触发条件

如果该问题影响玩家传送、NPC 行为观感或夜间回家睡觉闭环，再从以下方向处理：

1. 收窄 `NavigationTeleportPoint` / `NavigationTeleportLink` 的入口匹配半径。
2. 检查场景传送端点配置是否离视觉入口过远。
3. 通过 Unity MCP 调整传送点资产层配置。
