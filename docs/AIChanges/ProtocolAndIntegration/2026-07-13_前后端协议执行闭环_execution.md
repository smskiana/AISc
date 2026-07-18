# 前后端协议执行闭环执行记录

> 历史状态提示：本文“NPC-NPC 社交仍立即生成”的未完成项已于 [NPC 社交协议闭环](2026-07-14_NPC社交协议闭环_execution.md) 完成，不再代表当前状态。

> 设计方案: [plan.md](2026-07-13_前后端协议执行闭环_plan.md)

## 实际改动

### NPC 行为闭环

1. 后端 `NPC_BEHAVIOR` 增加 `request_id`，并记录同一 NPC 的最新待执行请求。
2. 后端发出行为时只更新 `current_action`，不再提前修改 `current_location`。
3. Unity 在移动成功、失败、取消以及 NPC / behavior 缺失时发送 `NPC_ACTION_RESULT`。
4. 后端返回 `NPC_ACTION_RESULT_ACK`；只有当前 request 的成功结果才提交实际位置。
5. Unity `GameStateStore` 同样改为到达成功后更新位置，避免前端缓存提前跳到目标地点。

### 玩家对话握手

1. `DIALOGUE_START` 调整为准备请求，携带 `request_id`。
2. 后端返回 `DIALOGUE_PREPARED`，Unity 确认本地会话仍有效后发送 `DIALOGUE_READY`。
3. 后端仅在 READY 后建立 active dialogue、暂停时间并生成首轮内容。
4. 对话准备阶段或首轮生成期间取消时会清理状态，不把准备提示写成真实互动记忆。

### 后端持续监听

1. READY 后的对话生成由运行时后台任务托管。
2. 同步 OpenAI 流通过工作线程读取，并用异步队列向事件循环转发 token。
3. LLM 流式生成期间 WebSocket 可以继续接收行为结果、取消和其他消息。
4. 运行时停止时会取消并清理后台协议任务。

## 实际涉及文件

- `backend/src/application/runtime.py`
- `backend/src/application/dialogue_service.py`
- `backend/src/dialogue/llm_client.py`
- `backend/src/npc/behavior_engine.py`
- `backend/tests/test_protocol_execution_loop.py`
- `Assets/Scripts/Core/GameCommandSender.cs`
- `Assets/Scripts/Core/GameManager.cs`
- `Assets/Scripts/Core/GameStateStore.cs`
- `Assets/Scripts/Data/MessageTypes.cs`
- `Assets/Scripts/NPC/NpcBehaviorApplier.cs`
- `Assets/Scripts/NPC/NpcSpawner.cs`

## 计划偏差

原计划新增独立 `NpcActionResultReporter.cs`。命令行编译发现 Unity 生成的 csproj 尚未收录新脚本；当前会话没有 Unity MCP，未修改 csproj 或触碰编辑器生成流程。Reporter 仍保持独立类职责，但暂时与 `NpcBehaviorApplier` 放在同一已收录文件中。

## 验证

1. `python -m unittest discover -s backend/tests -v`: 5 项通过。
2. `python -m compileall -q backend/src backend/tests`: 通过。
3. `dotnet build AISc.sln --no-restore`: 通过，0 error；保留既有程序集版本和未赋值字段警告。
4. `python backend/scripts/check_project_conventions.py`: 通过。

## 未完成项

1. 尚未在 Unity Play 模式验证真实移动成功、失败、取消和旧结果乱序日志。
2. NPC-NPC 社交仍是发送动作后立即生成数据，下一阶段应接入 `PREPARE / READY / CONTENT`。
3. 尚未加入统一 envelope、协议版本、sequence、重连快照和持久化幂等。
4. 玩家位置同步仍缺少显式 ACK 与重连校准。
