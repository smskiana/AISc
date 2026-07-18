> 执行记录: [2026-07-16_Unity项目专用AI诊断MCP工具_execution.md](2026-07-16_Unity项目专用AI诊断MCP工具_execution.md)

# Unity 项目专用 AI 诊断 MCP 工具 - 设计方案

## 需求理解

为 AI 提供可以直接通过 Unity MCP 调用的项目业务诊断入口，使其无需解析零散 Console 文本即可读取当前运行状态、系统健康、协议轨迹和 NPC 任务阶段。

本轮只实现只读诊断，不开放任意反射、任意字段写入、业务状态机绕过或正式存档修改。

## 当前工程口径

1. 所属主要功能域为测试与诊断，前端架构为关联功能域。
2. `GameManager` 保持 facade，不继续承接具体诊断聚合实现。
3. `WebSocketClient` 负责连接和收发，`ProtocolClient` 负责协议 session 与 sequence。
4. `NpcTaskExecutor` 负责 NPC 正式任务阶段和最近终态。
5. Unity MCP 已支持通过 `[McpForUnityTool]` 自动注册项目自定义工具。
6. 本轮不修改场景、Prefab、UI 或 SerializeField 连线。

## 方案

### 1. 单一 MCP 入口

新增 `aisc_debug` 项目工具，通过 `action` 路由以下只读操作：

- `runtime_snapshot`
- `health_report`
- `protocol_trace`
- `npc_task_snapshot`

MCP 适配器只负责参数校验与响应转换，运行时诊断逻辑放在独立 Diagnostics 模块中。

### 2. 运行时诊断模块

新增统一门面 `AiscDiagnostics`，对调用者提供少量稳定接口。各领域通过结构化快照暴露状态，不向 MCP 层泄漏内部字典或可变业务对象。

### 3. 协议轨迹

在 `ProtocolClient` 内维护固定容量环形轨迹，记录发送和接收 envelope 的方向、类型、request、session、sequence、时间和错误码。只保存协议元数据，不保存完整 payload，避免泄漏大量内容和无限增长。

### 4. NPC 任务快照

由 `NpcTaskExecutor` 导出只读任务快照，包含 NPC、request、阶段、进度版本、实际位置、移动锁和 active / terminal 状态。`NpcBehaviorApplier` 与 `NpcSpawner` 仅增加必要的逐层只读转发。

### 5. 健康判定

健康报告区分 `ready`、`degraded`、`failed`，覆盖 PlayMode、GameManager、WebSocket、协议协商、游戏状态和 NPC 注册入口。报告同时返回机器可读问题码和简短说明。

## 预计涉及文件

### 新增

- `Assets/Scripts/Diagnostics/README.md`
- `Assets/Scripts/Diagnostics/DiagnosticModels.cs`
- `Assets/Scripts/Diagnostics/AiscDiagnostics.cs`
- `Assets/Scripts/Editor/Diagnostics/AiscDebugMcpTool.cs`
- `Assets/Tests/EditMode/Aisc.Diagnostics.EditModeTests.asmdef`
- `Assets/Tests/EditMode/AiscDiagnosticsTests.cs`

### 修改

- `Assets/Scripts/Protocol/ProtocolClient.cs`
- `Assets/Scripts/NPC/NpcTaskExecutor.cs`
- `Assets/Scripts/NPC/NpcBehaviorApplier.cs`
- `Assets/Scripts/NPC/NpcSpawner.cs`
- `Assets/Scripts/Core/GameManager.cs`
- `Assets/Scripts/README.md`
- `docs/Workstreams/FrontendArchitecture/README.md`
- `docs/AIChanges/TestingAndDiagnostics/README.md`

## 风险与控制

1. Unity Editor 编译域依赖 MCP 包：适配器限定在 `Assets/Scripts/Editor/`。
2. 运行时模块不可依赖 Editor 或 MCP 命名空间，保证 Player 编译不受影响。
3. 协议轨迹限制容量且不保存 payload，避免内存和敏感内容膨胀。
4. NPC 快照复制为 DTO，不返回内部任务对象。
5. EditMode 下没有运行中 GameManager 时，返回结构化 `play_mode_required` 或 `game_manager_missing`，不得抛空引用异常。
6. 不增加场景对象或运行时自动挂载，不引入资产层兜底。

## 验证方式

1. Unity MCP 显式导入新增脚本并等待编译完成。
2. Unity Console 0 error。
3. EditMode 测试覆盖协议轨迹容量、筛选和 NPC 任务空快照等纯逻辑。
4. Unity MCP 的 `custom-tools` 资源能发现 `aisc_debug`。
5. EditMode 调用返回明确错误；PlayMode 调用四个 action 返回结构化结果。

