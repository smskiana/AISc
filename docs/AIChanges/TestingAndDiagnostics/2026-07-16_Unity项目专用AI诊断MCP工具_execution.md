> 设计方案: [2026-07-16_Unity项目专用AI诊断MCP工具_plan.md](2026-07-16_Unity项目专用AI诊断MCP工具_plan.md)

# Unity 项目专用 AI 诊断 MCP 工具 - 执行记录

## 实际改动

1. 新增运行时诊断深模块 `AiscDiagnostics`，聚合运行快照、健康报告、协议轨迹和 NPC 任务快照。
2. 新增项目专用 Unity MCP 工具 `aisc_debug`，使用单一入口和 action 路由，不暴露任意反射或状态写入。
3. `ProtocolClient` 新增固定容量 200 条的 envelope 元数据轨迹，支持 request_id 过滤和最近条数限制；不保存完整 payload。
4. `NpcTaskExecutor` 新增活动任务与最近终态的只读 DTO 导出，并由 `NpcBehaviorApplier`、`NpcSpawner` 提供最小转发。
5. `UnitySaveService` 新增事务阶段和活动 checkpoint 的只读属性，供诊断快照使用。
6. 新增 4 个 EditMode 测试，覆盖非 PlayMode 健康报告、无 GameManager 空轨迹、request_id 筛选和固定容量。

## 实际文件

### 新增

- `Assets/Scripts/Diagnostics/README.md`
- `Assets/Scripts/Diagnostics/DiagnosticModels.cs`
- `Assets/Scripts/Diagnostics/AiscDiagnostics.cs`
- `Assets/Scripts/Editor/Diagnostics/AiscDebugMcpTool.cs`
- `Assets/Tests/Editor/AiscDiagnosticsTests.cs`
- `docs/AIChanges/TestingAndDiagnostics/2026-07-16_Unity项目专用AI诊断MCP工具_plan.md`
- `docs/AIChanges/TestingAndDiagnostics/2026-07-16_Unity项目专用AI诊断MCP工具_execution.md`

### 修改

- `Assets/Scripts/Protocol/ProtocolClient.cs`
- `Assets/Scripts/NPC/NpcTaskExecutor.cs`
- `Assets/Scripts/NPC/NpcBehaviorApplier.cs`
- `Assets/Scripts/NPC/NpcSpawner.cs`
- `Assets/Scripts/Save/UnitySaveService.cs`
- `Assets/Scripts/README.md`
- `Assets/Scripts/Protocol/README.md`
- `Assets/Scripts/NPC/README.md`
- `docs/Workstreams/FrontendArchitecture/README.md`
- `docs/AIChanges/TestingAndDiagnostics/README.md`

计划中的独立测试 asmdef 未创建。测试放入现有 `Assembly-CSharp-Editor`，因为该预定义编辑器程序集已引用 NUnit 和 Unity Test Runner，并且可以直接访问 `Assembly-CSharp` 中的运行时类型。

## Unity MCP 操作

1. 使用 `manage_asset import` 显式导入新增 C# 文件并生成 `.meta`。
2. 等待 Unity 域重载结束，确认编辑器处于 idle。
3. 从 `mcpforunity://custom-tools` 确认 `aisc_debug` 已注册，自定义工具数量由 34 增至 35。
4. 通过 `run_tests` 执行 `AiscDiagnosticsTests`。
5. 进入 `Town_Main` PlayMode，实际读取四类诊断结果，之后退出 PlayMode。

## 验证结果

1. Unity Console：0 error。
2. EditMode：4 passed，0 failed。
3. 非 PlayMode 健康报告返回 `failed / play_mode_required`。
4. PlayMode 运行快照成功返回场景、时间、暂停、连接、协议 session、存档阶段和 NPC 数量。
5. PlayMode 健康报告在游戏尚未 ready 时返回 `degraded / gameplay_not_ready`。
6. 协议轨迹实际捕获 hello、hello_ack、world_snapshot、world_snapshot_applied。
7. NPC 任务为空时返回稳定空集合。

## 未完成项

1. 等待条件与断言 action。
2. 导航主动探测。
3. 截图、Console 和诊断快照证据打包。
4. 受控调试命令；当前工具保持完全只读。

