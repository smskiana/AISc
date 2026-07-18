> 设计方案: [2026-07-12_阶段路线图排期_plan.md](2026-07-12_阶段路线图排期_plan.md)

# 阶段路线图排期执行记录

## Workstream

ProjectGovernance / FrontendArchitecture / Navigation

## Roadmap item

GOV / FEA / NAV / DIA

## 相关 ADR

1. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`
2. `docs/DecisionRecords/ADR-0003-unity-mcp-asset-first.md`

## 实际改动清单

### 1. 更新 Roadmap 三档排期

更新 `docs/Roadmap.md`，新增“三档排期”：

1. 正在进行：
   - 前端架构失衡修复。
   - 导航与移动闭环验证。
   - 协议与存档底座设计。

2. 正在计划：
   - 玩家传送 / 场景入口能力。
   - 玩家基础 UI，严格 MVC。
   - 夜间日常闭环。
   - NPC 见闻与社交互动。

3. 未来要做：
   - 模拟经营店铺核心循环。
   - 送礼系统。
   - 交易系统。
   - 耕种系统。
   - 街机系统。

同时在冻结事项中追加：不在协议和存档底座稳定前推进复杂经营系统。

### 2. 同步前端职责工作流

更新 `docs/Workstreams/FrontendArchitecture/README.md`：

1. 下一阶段建议中补充玩家基础 UI、玩家传送、玩家插入 NPC 对话的顺序。
2. 新增当前阶段排期，分为正在进行、正在计划、未来要做。
3. 暂缓事项中补充：不在协议和存档底座稳定前推进复杂经营系统。

### 3. 同步导航工作流

更新 `docs/Workstreams/Navigation/README.md`：

1. 下一阶段建议中补充玩家传送 / 场景入口能力。
2. 新增“玩家传送排期口径”。
3. 明确玩家传送不直接塞进 `AStarMovementProvider`。
4. 明确玩家传送应复用 location id、SceneAnchor 和 NavigationTeleportPoint 语义。

### 4. 回写 ChangeIndex

更新 `docs/AIChanges/ChangeIndex.md`：

1. 在项目治理分组登记本轮路线图排期。
2. 在前端职责与 Unity 资产分组登记本轮路线图排期。

## 遇到的问题

无。

## 验证方式

1. 静态检查 `docs/Roadmap.md` 中存在：
   - `### 正在进行`
   - `### 正在计划`
   - `### 未来要做`
2. 静态检查玩家传送已进入 `docs/Roadmap.md` 与 `docs/Workstreams/Navigation/README.md`。
3. 静态检查本轮 plan / execution 已回写 `docs/AIChanges/ChangeIndex.md`。

本轮只修改文档，不涉及代码编译。

## 未完成项

1. 尚未把三档排期拆成具体执行任务。
2. 尚未为玩家传送、协议优化、存档可靠性分别生成详细设计方案。
