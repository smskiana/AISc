# 暂停系统三时间域执行记录

> 设计方案: [2026-07-17_暂停三时间域_plan.md](2026-07-17_暂停三时间域_plan.md)

## 1. 实际改动

1. 新增 `PauseTimeDomain`，固定提供 `Gameplay`、`UI`、`FX` 三个 flags 时间域。
2. 新增 `PauseSourcePolicy`，集中映射暂停来源；现有业务来源与固定诊断来源均暂停 Gameplay 和 FX，不暂停 UI。
3. `PauseModel` 改为保存来源及其时间域，支持跨域独立状态和同域多来源引用语义。
4. `PauseController` 保留原申请/释放接口，新增分域查询、分域来源快照和域变化事件；`Time.timeScale` 与 Python 暂停同步只响应 Gameplay 域。
5. 新增 `PauseClock`，将 `PortraitDialogueUI`、`BubbleUI`、`SystemMessageController` 的动效/显示计时迁入 UI 域。气泡自动隐藏不再使用受 Gameplay 冻结的 `WaitForSeconds`。
6. `GameTimeController` 与 `PlayerController` 的显式暂停判断改查 Gameplay 域。
7. 新增 `PauseFxAdapter`：明确连线的 ParticleSystem 使用非缩放时间，Animator 使用 `UnscaledTime`；FX 域暂停时只记录并恢复由适配器暂停的实例。
8. `aisc_debug.runtime_snapshot.pause` 新增三域状态、各域来源、`Time.timeScale`、受管 FX 总数和域暂停 FX 数量。
9. `aisc_control` 新增固定白名单 `request_pause_test` / `release_pause_test`，只使用 `diagnostics_test` 稳定来源，不开放任意来源、任意域或反射控制。
10. 新增分域 EditMode 测试并扩展诊断 DTO 测试。

## 2. Unity MCP 资产结果

1. 执行前已读取 `UnityMCPUsageRules.md`，并连接 `AISc@9db8baa7dcf9cfcd`（Unity `2022.3.62t7`）。
2. 通过 Unity 反射确认 `ParticleSystem.MainModule.useUnscaledTime` 和 `Animator.updateMode` 可读写。
3. 通过 Unity MCP 查询当前 `Town_Main` 场景，ParticleSystem 与 Animator 实例均为 0，因此没有可挂载或连线的 FX 资产；未创建占位对象，也未用运行时全场景扫描兜底。
4. 新建 C# 文件已通过 Unity MCP 显式导入 AssetDatabase，并完成脚本刷新和域重载。

## 3. 诊断与验证

1. Unity Console：项目编译错误 0；脚本刷新期间出现一次 MCP WebSocket 重连警告，不属于项目代码错误。
2. EditMode：`PauseTimeDomainTests` 与 `AiscDiagnosticsTests` 共 16 项，16 通过、0 失败、0 跳过。
3. Play + `aisc_control.request_pause_test`：`aisc_debug.runtime_snapshot.pause` 报告：
   - `gameplay_paused = true`
   - `ui_paused = false`
   - `fx_paused = true`
   - `unity_time_scale = 0`
   - Gameplay/FX 来源均为 `diagnostics_test`
4. Play + `aisc_control.release_pause_test`：三域均恢复为 false，来源清空，`unity_time_scale = 1`。
5. FX 诊断计数为 0，与当前场景无 FX 实例的 Unity MCP 盘点一致。

## 4. 文档与索引回写

1. 新增 `Assets/Scripts/Pause/README.md` 作为暂停代码目录入口。
2. 更新 `Assets/Scripts/README.md`、前端 Workstream 和 TestingAndDiagnostics README。
3. 未改变 ADR、Roadmap、协议 schema 或存档口径。

## 5. 未完成项

1. 当前场景没有 ParticleSystem/Animator FX，无法进行真实 FX 播放中暂停/恢复视觉验收。未来引入 FX 资产时，必须通过 Unity MCP 将其接入 `PauseFxAdapter` 并补 Play 回归。
2. 本轮只迁移明确属于 UI 动效的消费者；NPC 世界气泡队列、任务动作和协议真实时间保持原语义，未做机械替换。
