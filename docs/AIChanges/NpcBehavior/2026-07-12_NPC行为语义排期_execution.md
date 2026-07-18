> 设计方案: [2026-07-12_NPC行为语义排期_plan.md](2026-07-12_NPC行为语义排期_plan.md)

# NPC 行为语义排期执行记录

## Workstream

NpcBehavior / FrontendArchitecture / Navigation

## Roadmap item

NPC / FEA / NAV

## 相关 ADR

1. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`
2. `docs/DecisionRecords/ADR-0003-unity-mcp-asset-first.md`

## 实际改动清单

### 1. 新增 NPC 行为工作流

新增 `docs/Workstreams/NpcBehavior/README.md`：

1. 明确目标是让 NPC 在对的时间、对的位置、做对的事情。
2. 区分导航系统和 NPC 行为系统：
   - 导航回答能不能到、怎么到、是否到达。
   - NPC 行为回答为什么去、去哪里、在那里做什么、做成没有。
3. 记录当前问题：
   - NPC 行为偏随机。
   - 日计划可能出现非法空 location。
   - 前端 spot / anchor 不够细。
   - `NpcSpawner` 仍承担行为解释职责。
   - 行为结果回报尚未稳定。
4. 记录下一阶段建议：
   - action-location affordance 表。
   - 后端行为计划约束。
   - `NpcBehaviorApplier`。
   - 行为结果反馈。
   - Play 模式诊断。

### 2. 更新 Roadmap

更新 `docs/Roadmap.md`：

1. 当前路线图表新增 NPC 行为工作流。
2. “正在进行”新增 NPC 行为语义收敛。
3. “正在计划”新增 NPC 行为 spot / action affordance 细化。
4. 冻结事项新增：不用“随机可达点”替代 NPC 行为语义。

### 3. 同步工作流索引

更新 `docs/Workstreams/README.md`：

1. 新增 NPC 行为入口。

更新 `docs/Workstreams/FrontendArchitecture/README.md`：

1. 下一阶段建议加入 NPC 行为语义从 `NpcSpawner` 中拆出。
2. 当前阶段排期加入 NPC 行为语义收敛。
3. 正在计划加入 NPC 行为 spot / action affordance 细化。
4. 相关入口加入 NPC 行为工作流。

更新 `docs/Workstreams/Navigation/README.md`：

1. 明确导航只回答能不能到、怎么到、是否到达。
2. NPC 是否应该去某处、在那里做什么，归 NPC 行为工作流维护。
3. 暂缓事项新增：不用随机可达点替代 NPC 行为语义。

### 4. 回写 ChangeIndex 与 handoff

更新 `docs/AIChanges/ChangeIndex.md`：

1. 新增 NPC 行为分组。
2. 登记本轮 NPC 行为语义排期。
3. 将已有“记忆驱动行为与印象决策重构”登记为相关历史证据。

更新 `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-12.md`：

1. 补充阶段路线与 NPC 行为语义排期状态。
2. 将本轮 plan / execution 加入最近关键执行记录。

## 遇到的问题

1. 第一次合并补丁试图同时修改多个文档并插入 ChangeIndex，因插入位置不匹配失败。
2. 已拆成小补丁逐项更新，避免误改周边内容。

## 验证方式

1. 静态检查 `docs/Workstreams/NpcBehavior/README.md` 存在。
2. 静态检查 `docs/Roadmap.md` 中存在：
   - `NPC 行为`
   - `NPC 行为语义收敛`
   - `NPC 行为 spot / action affordance 细化`
3. 静态检查 `docs/AIChanges/ChangeIndex.md` 中存在 NPC 行为分组和本轮记录。
4. 静态检查 `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-12.md` 中已登记本轮排期。

本轮只修改文档，不涉及代码编译。

## 未完成项

1. 尚未设计 action-location affordance 数据结构。
2. 尚未拆 `NpcBehaviorApplier`。
3. 尚未修日计划非法空 location。
4. 尚未实现行为结果回报协议。
