> 执行记录: [2026-07-10_原生WebSocket联调_execution.md](2026-07-10_原生WebSocket联调_execution.md)

# 原生 WebSocket 联调 — 设计方案

## 完成时间
2026-07-10

## 需求理解

当前前后端业务职责本身已经基本清晰：

1. Python 负责记忆、状态、行为决策、对话生成、时钟和午夜编排
2. Unity 负责场景锚点、角色表现、输入、UI、气泡和点击交互

真正不清晰的是通信层：

1. 后端同时保留原生 `/ws` 和 HTTP 桥接 `/api/ws + /api/poll`
2. Unity 实际跑的是桥接模式
3. 后端有些消息只会发给活动 WebSocket，例如 `SLEEP_TRIGGER`、`WAKE_UP`
4. 导致“主链能跑，但异步推送类事件不完整”

因此这轮的目标不是再调整业务边界，而是把通信层重新收敛成单一的原生 WebSocket。

## 当前判断

### 职责划分是否清晰

结论：**清晰，可以切回原生 WebSocket。**

原因：

1. 后端没有侵入 Unity 场景逻辑，仍只发语义消息和 `location_id`
2. Unity 已经有 `SceneAnchorRegistry` / `LocationDatabase` 负责把 `location_id` 落到场景坐标
3. 玩家输入、点 NPC 对话、表现层移动都在 Unity
4. 后端应用层已经在上一轮重构中收敛为 `GameRuntime + MessageBus + DialogueService`

所以现在改通信层，不会破坏已有职责边界，反而会让边界更干净。

## 改造目标

1. Unity `WebSocketClient` 改为真正连接 `ws://127.0.0.1:8766/ws`
2. 不再依赖 `/api/ws` 和 `/api/poll` 完成主通信链路
3. 让 `SLEEP_TRIGGER / WAKE_UP / NPC_BEHAVIOR / NPC_BUBBLE / NPC_SOCIAL_ACTION` 全部走同一条推送链
4. 顺手补齐当前前端未接的协议消息：
   - `LOAD_COMPLETE`
   - `GAME_TIME_UPDATE`
5. 把玩家位置上报职责补回 Unity 侧

## 涉及文件

1. `Assets/Scripts/Core/WebSocketClient.cs`
2. `Assets/Scripts/Data/MessageTypes.cs`
3. `Assets/Scripts/Core/GameManager.cs`
4. `Assets/Scripts/Core/PlayerController.cs`
5. `docs/AIChanges/ProtocolAndIntegration/2026-07-10_原生WebSocket联调_plan.md`
6. `docs/AIChanges/ProtocolAndIntegration/2026-07-10_原生WebSocket联调_execution.md`

## 方案

### 1. Unity 通信客户端切回原生 WebSocket

优先采用 .NET 自带 `ClientWebSocket`：

1. 项目是 PC 单机，不考虑 WebGL 限制
2. 当前 `Packages/manifest.json` 里没有现成 `NativeWebSocket`
3. 直接引第三方包不是这轮最小修改

实现要求：

1. 启动时仍可先打 `/api/health` 做 readiness 检查
2. 检查通过后建立持久 WebSocket 连接
3. 后台接收消息，主线程分发给 Unity 回调
4. 发送消息统一走同一条 WS 通道

### 2. 补齐协议分发缺口

`MessageTypes.cs` 需要新增：

1. `LoadCompleteMsg`
2. `GameTimeUpdateMsg`

并在 `MessageRouter` 中增加对应 `case`。

### 3. GameManager 统一接收新增消息

补充对：

1. `LOAD_COMPLETE`
2. `GAME_TIME_UPDATE`

的处理，至少保证：

1. `CurrentTime` 正确刷新
2. 前端日志可见

### 4. 玩家位置同步补回 Unity 职责

`PlayerController` 用 `SceneAnchorRegistry.TryResolveNearestLocation()` 在玩家移动时解析最近 `location_id`，并通过 `GameManager` 上报：

```json
{"type":"PLAYER_MOVE","location_id":"..."}
```

这样“玩家在不在附近”的判断重新回到正确职责划分：

1. Unity 负责世界坐标和场景点位
2. Python 只负责语义位置和基于位置的决策

## 不做的事

这轮不做：

1. 删除后端 `/api/ws` 或 `/api/poll`
2. 改数据库 schema
3. 调整行为规则或记忆模型
4. 重做存档协议

保留 `/api/health` 作为联通性检查和调试入口。

## 验证计划

1. 代码层检查：
   - Unity 通信入口不再依赖轮询主链
   - `MessageRouter` 能分发新增消息
2. 逻辑检查：
   - `SLEEP_TRIGGER / WAKE_UP` 现在具备到达 Unity 的通道
   - 玩家移动可以上报 `PLAYER_MOVE`
3. 文档记录：
   - 写 execution，标明当前仍未实际做 Unity Play 联调的部分
