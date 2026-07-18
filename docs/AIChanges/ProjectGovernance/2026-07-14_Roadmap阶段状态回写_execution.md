# Roadmap 阶段状态回写执行记录

> 设计方案: [plan.md](2026-07-14_Roadmap阶段状态回写_plan.md)

## 实际改动

1. 更新 `docs/Roadmap.md` 当前阶段表，标记功能索引、前端第一阶段拆分、移动结果闭环和对话准备握手已经落地。
2. 在 Roadmap 新增“已完成底座”，集中记录已经具备执行证据的能力。
3. 将“正在进行”收敛为 Play 回归、NPC 行为语义约束、协议与存档底座，不再重复列出已完成拆分类。
4. 更新 FrontendArchitecture、Navigation、NpcBehavior、Dialogue、ProjectGovernance Workstream 的当前口径、已完成阶段和下一步。
5. 更新 Workstream 总索引和各功能证据入口，移除旧的 ChangeIndex 分组表述。

## 状态变化

- `GameCommandSender`、`GameStateStore`、`NpcBehaviorApplier`、`NpcSocialRendezvousController`：从待拆改为已完成。
- 移动成功 / 失败 / 取消与成功后提交位置：从待实现改为已完成，保留 Play 回归。
- NPC 行为 request/result 和玩家对话 PREPARED/READY：从协议预留改为第一阶段已完成。
- transit 位置和前端空闲表现：写入当前工程口径，保留运行观感验证。
- 项目功能索引治理：从建设阶段改为维护阶段。

## 保留的未完成项

1. Unity Play 模式跨店、取消、失败、旧结果乱序和 transit 验证。
2. action-location-time-role、spot affordance、非法空 location 治理。
3. 行为超时、重试和改计划策略。
4. 统一协议 envelope、版本、sequence、重连快照与幂等。
5. 存档职责边界、玩家传送、基础 UI 和夜间闭环。

## 验证结果

1. 已完成的四个拆分类名不再出现在 Roadmap 或 Workstream 的待拆列表。
2. Workstream 中不存在旧的 `ChangeIndex.md` 功能分组引用。
3. 本轮涉及文档的本地链接有效；plan 与 execution 已互链。

## 未完成项

无。
