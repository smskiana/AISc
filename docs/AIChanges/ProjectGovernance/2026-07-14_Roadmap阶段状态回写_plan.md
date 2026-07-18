# Roadmap 阶段状态回写方案

> 执行记录: [execution.md](2026-07-14_Roadmap阶段状态回写_execution.md)

## 需求理解

Roadmap 和部分 Workstream 仍把已经完成的前端职责拆分、移动结果语义和协议闭环列为待办。本轮根据已有 execution 证据更新当前阶段，不新增功能、不扩大排期。

## 所属 Workstream / Roadmap

- Workstream: `ProjectGovernance`
- Roadmap item: GOV，并同步 FEA、NAV、NPC、DIA 的阶段状态
- 相关 ADR: ADR-0002、ADR-0005；本轮不改变 ADR 口径

## 已确认的完成证据

1. `GameCommandSender`、`GameStateStore`、`NpcBehaviorApplier`、`NpcSocialRendezvousController` 已完成拆分。
2. `IMovementProvider` 已支持成功、失败、取消，位置只在成功后提交。
3. NPC 行为 request/result 闭环已接通，并能拒绝旧 request。
4. 玩家对话 PREPARED/READY 握手和 LLM 生成期间持续监听已完成。
5. NPC 移动期间的 transit 权威位置语义已完成。
6. 后端随机微动作已停止，前端空闲表现层已接管可抢占的小动作和同区域踱步。
7. 项目功能索引重构已经完成。

## 修改范围

- `docs/Roadmap.md`
- `docs/Workstreams/README.md`
- `docs/Workstreams/FrontendArchitecture/README.md`
- `docs/Workstreams/Navigation/README.md`
- `docs/Workstreams/NpcBehavior/README.md`
- `docs/Workstreams/Dialogue/README.md`
- `docs/Workstreams/ProjectGovernance/README.md`

## 更新原则

1. 只有存在 execution 证据的事项才标记完成。
2. Play 模式观察、超时重试、统一 envelope、重连快照、玩家传送和存档边界继续保留为未完成。
3. 不把单次执行细节复制进 Roadmap，只更新阶段和下一步。

## 验证

1. 搜索已完成类名，确认不再出现在“待拆 / 正在进行”列表。
2. 检查 Roadmap 与各 Workstream 的阶段描述一致。
3. 检查新增 plan / execution 互链和 Markdown 本地链接。
