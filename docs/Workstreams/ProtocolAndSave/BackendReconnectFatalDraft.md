# 后端重启被错误升级为致命退出草案

## 定位

本文件记录 2026-07-19 NPC 日程真实 PlayMode 验收中暴露的连接恢复缺口，只用于后续方案设计和问题追踪，不是 implementation plan，不授权修改运行代码。

## 复现步骤

1. 启动 Python 后端和 `Town_Main`，进入新游戏并等待 `gameplay_ready=true`。
2. 保持 Unity Play Mode，停止 Python 后端。
3. 重新启动 Python 后端。

## 实际结果

1. Unity 收到 `The remote party closed the WebSocket connection without completing the close handshake.`。
2. `WebSocketClient.ReceiveLoopAsync` 只设置 `IsConnected=false`、`IsConnecting=false`。
3. `WebSocketClient.Update` 触发 `Disconnected`，但没有调用 `BeginConnect`。
4. `FatalErrorController` 在 gameplay ready 后把任意断线立即升级为只能退出桌面的阻塞错误。
5. `aisc_debug` 显示暂停来源为 `blocking_message`，协议轨迹没有第二次 `hello`，因此 world snapshot 和同日剩余日程恢复均未开始。

## 期望结果

可恢复的意外断线先进入有界重连流程：重新健康检查、建立 WebSocket、完成新 session 握手、发送 Unity 权威 world snapshot，并恢复同日剩余日程。只有重试耗尽、协议不兼容或世界快照拒绝等不可恢复失败才进入致命退出。

## 已确认边界

1. 根因位于 Unity 连接恢复状态机与致命错误升级策略，不是本轮日程 planner、revision 或恢复 DTO 本身。
2. Unity 仍持有 `schedule_day=1`、`schedule_revision=1` 和剩余日程；故障发生在重连前。
3. 修复不得允许断线期间继续推进依赖后端的业务；应使用独立连接恢复暂停来源，而不是复用最终致命弹窗。
4. 新连接必须重新执行 `hello / hello_ack`，不能沿用旧 session 或 sequence。
5. 重连后的 world snapshot 必须继续遵守 ADR-0006 的 Unity 世界权威边界。

## 待设计问题

1. 最大重试次数、退避时间和玩家提示口径。
2. 断线时正在执行的 NPC 任务、对话、社交 session 和 pending replan 如何冻结或终态化。
3. 新 session 建立后，哪些临时请求可以重放，哪些必须以新 operation 重建。
4. 重连成功、重试中、重试耗尽和 world snapshot 拒绝的 `aisc_debug` DTO 与稳定失败码。
5. 小于 30 秒的断线/重启回归 seam，以及真实 PlayMode 长链验收步骤。

## 相关入口

- `Assets/Scripts/Core/WebSocketClient.cs`
- `Assets/Scripts/SystemMessages/FatalErrorController.cs`
- `Assets/Scripts/Protocol/ProtocolClient.cs`
- `backend/src/protocol/session.py`
- `backend/src/application/runtime.py`
- `docs/DecisionRecords/ADR-0006-unity-authoritative-save-memory-checkpoint.md`

## 相关验收发现

新游戏未清理 Python 日程快照及运行时 replan 错误循环见 `docs/Workstreams/NpcBehavior/DailySchedulePlayModeFindingsDraft.md`。
