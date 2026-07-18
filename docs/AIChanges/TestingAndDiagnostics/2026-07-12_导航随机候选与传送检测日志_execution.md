> 设计方案: [2026-07-12_导航随机候选与传送检测日志_plan.md](2026-07-12_导航随机候选与传送检测日志_plan.md)

# 导航随机候选与传送检测日志执行记录

## Workstream

Navigation / FrontendArchitecture

## Roadmap item

NAV / FEA

## 相关 ADR

1. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`

## 实际改动清单

### 1. 候选点随机性日志

修改 `Assets/Scripts/Navigation/NavigationDebugLog.cs`：

1. 新增 `LogLocationCandidateBatch()`：
   - 输出 `候选点批次`。
   - 包含 location、count、近似唯一点数量、bbox、前 16 个 raw 候选点。
   - 用于连续触发同一 location 移动时检查 raw 坐标是否变化。

2. 新增 `LogLocationCandidateEvaluation()`：
   - 输出 `候选评估`。
   - 包含 raw 坐标、raw cell、resolved cell、resolved world、rawDelta、成功 / 失败原因、路径段数、传送段数。

3. 新增 `LogSelectedLocationCandidate()`：
   - 输出 `选中候选`。
   - 记录本次 raw / resolved / teleports。
   - 和同 NPC 上一次同 location 的选中 raw 点对比，输出 `previousDelta`。

修改 `Assets/Scripts/Navigation/AStarMovementProvider.cs`：

1. `MoveToLocation()` 获取候选点后立即输出候选批次。
2. 每个候选点寻路后输出评估结果。
3. 最终成功候选输出选中日志。
4. 新增私有 `CandidatePathProbe`，只保存候选点检测用的 raw cell 与 resolved target，不改变移动逻辑。

### 2. 传送稳定触发日志

修改 `Assets/Scripts/Navigation/NavigationDebugLog.cs`：

1. `LogPathSummary()` 的 `TELEPORT` 行新增：
   - `enterFrom`
   - `entrance`
   - `entranceDistance`
   - `configuredExit`
   - `resolvedExit`
   - `exitSnapDistance`
   - `reverse`

修改 `Assets/Scripts/Navigation/AStarMovementProvider.cs`：

1. `MoveAlongPath()` 执行传送段时新增：
   - `actualFrom`
   - `entrance`
   - `entranceDistance`
   - `configuredExit`
   - `resolvedExit`
   - `exitSnapDistance`
   - `reverse`

这能区分“真的执行 typed Teleport segment”与“普通长距离行走”。

## Play 验收看点

1. 同一 NPC 多次移动到同一 location：
   - 看 `候选点批次` 的 `samples` 是否变化。
   - 看 `unique≈` 是否大于 1。
   - 看 `选中候选` 的 `previousDelta` 是否经常大于 0。

2. 候选点落到障碍附近：
   - 看 `候选评估` 的 `rawDelta`。
   - `rawDelta` 很大说明 raw 点被吸附到较远可走格，需要回看 SceneAnchor 区域或导航烘焙。

3. 跨店 / 店内到街道移动：
   - `路径摘要` 中应出现 `TELEPORT link=...`。
   - 随后应出现 `执行传送段 link=...`。
   - `entranceDistance` 应较小；如果很大，说明传送入口匹配范围或路径段端点需要继续查。
   - `exitSnapDistance` 过大时，说明出口点和最近可走格偏离较远。

## 验证方式

1. 静态搜索新增日志关键字：
   - `候选点批次`
   - `候选评估`
   - `选中候选`
   - `执行传送段`
   - `entranceDistance`
2. 执行 `dotnet build AISc.sln --no-restore`：
   - 0 error
   - 8 warning，仍为既有 Unity / .NET 引用冲突、JSON 字段未赋值、`GameManager._serverUrl` 未使用。
3. Unity MCP：
   - `refresh_unity(scope=scripts, compile=request, wait_for_ready=true)` 成功；过程中曾断连并自动恢复。
   - `validate_script Assets/Scripts/Navigation/AStarMovementProvider.cs`：0 error / 0 warning。
   - `validate_script Assets/Scripts/Navigation/NavigationDebugLog.cs`：0 error / 0 warning。

## 遇到的问题

Unity Console 当前仍有既有非脚本编译错误：

1. `Import Error Code:(4)`
2. 多条 `The referenced script (Unknown) on this Behaviour is missing!`

本轮只改导航日志脚本，MCP 单文件校验和命令行编译均通过；上述 Console 错误需要后续单独定位资产缺失脚本或导入问题。

## 未完成项

1. 尚未进行 Play 模式实际路线长测。
2. 尚未根据日志调整 SceneAnchor 区域、传送点半径或导航烘焙。
3. 尚未处理 Console 中既有的 missing script / import error。
