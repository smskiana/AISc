> 设计方案: [2026-07-13_导航候选选点随机性修复_plan.md](2026-07-13_导航候选选点随机性修复_plan.md)

# 导航候选选点随机性修复执行记录

## Workstream

Navigation / FrontendArchitecture

## Roadmap item

NAV / FEA

## 相关 ADR

1. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`

## 实际改动清单

### 1. 调整 SceneAnchor 候选顺序

修改 `Assets/Scripts/Data/SceneAnchor.cs`：

1. `SampleCandidatePoints()` 不再先把区域中心点或 Anchor 中心点放入 `results`。
2. 新增 `fallbackPoints`，收集每个启用区域的中心点，或无自定义区域时的 Anchor 中心点。
3. 先通过 `SamplePoint(fallbackRadius)` 生成指定数量的随机候选点。
4. 最后 `AddRange(fallbackPoints)`，把固定中心点作为随机候选都不可达后的兜底。

这样保留 `AStarMovementProvider` 的“第一条可达路径即选中”策略，同时让 `candidate#0` 进入随机分布，避免固定中心点长期抢占优先级。

## 验证方式

1. 静态搜索确认：
   - `fallbackPoints`
   - `随机点优先`
   - `results.AddRange(fallbackPoints)`
2. 执行 `dotnet build AISc.sln --no-restore`：
   - 0 error
   - 8 warning，仍为既有 Unity / .NET 引用冲突、JSON 字段未赋值、`GameManager._serverUrl` 未使用。
3. Unity MCP：
   - 已读取 `mcpforunity://custom-tools` 和 `mcpforunity://editor/state`。
   - `refresh_unity(scope=scripts, compile=request, wait_for_ready=true)` 成功；过程中曾断连并自动恢复。
   - `validate_script Assets/Scripts/Data/SceneAnchor.cs`：0 error / 0 warning。
   - Console error：0。
   - Console warning：2，分别为既有 `GameManager._serverUrl` 未使用和 MCP WebSocket warning。

## Play 验收标准

1. 同一 NPC 多次移动到同一 location 时，`候选点批次 samples=#0` 应不再长期等于固定中心点。
2. `选中候选 candidate#0 raw=...` 应随批次变化。
3. `previousDelta` 应经常大于 `0.000`。
4. 若出现大量候选不可达，再回看对应 `SceneAnchor` 区域是否过宽或导航烘焙是否把可站区域切断。

## 遇到的问题

Unity MCP 刷新脚本时出现一次断连，但工具自动恢复并返回 editor ready。

## 未完成项

1. 尚未重新进入 Play 模式确认 `previousDelta` 已变化。
2. 尚未处理传送入口触发偏宽问题；该问题已在 `2026-07-12_传送入口触发偏宽记录_execution.md` 中单独记录。
