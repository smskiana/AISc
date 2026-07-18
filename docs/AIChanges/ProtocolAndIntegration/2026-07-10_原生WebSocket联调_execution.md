> 设计方案: [2026-07-10_原生WebSocket联调_plan.md](2026-07-10_原生WebSocket联调_plan.md)

# 原生 WebSocket 联调 — 执行记录

## 完成时间
2026-07-10

## 结论

### 前后端职责划分

结论：**职责划分清晰，不需要重切业务边界，只需要收敛通信主链。**

当前边界可归纳为：

1. Python 负责记忆图、状态、行为/对话决策、游戏时钟、午夜结算
2. Unity 负责场景坐标、Anchor、移动表现、输入、UI、气泡和交互
3. 双方通过 `location_id + 语义消息` 交互，而不是让后端直接控制场景对象

问题点不在职责，而在之前通信层同时存在：

1. `/ws`
2. `/api/ws`
3. `/api/poll`

导致 Unity 主链跑在 HTTP 桥接上，而后端部分异步消息只发给活动 WebSocket，出现“能启动但异步事件不完整”。

## 实际改动

### 修改文件 (4)

| 文件 | 改动 |
|------|------|
| `Assets/Scripts/Core/WebSocketClient.cs` | Unity 主链从 HTTP 桥接改为原生 `ClientWebSocket`；保留 `/api/health` 检查；后台接收、主线程分发；新增连接失败状态字段 |
| `Assets/Scripts/Data/MessageTypes.cs` | 补齐 `LOAD_COMPLETE`、`GAME_TIME_UPDATE` 消息类型与回调 |
| `Assets/Scripts/Core/GameManager.cs` | 注册新增消息回调；新增 `SendPlayerMove()`；启动时改为“等连接或等失败”，避免 WS 握手失败时无限等待 |
| `Assets/Scripts/Core/PlayerController.cs` | 根据场景 Anchor 反查最近 `location_id`，节流上报 `PLAYER_MOVE` |

## 关键实现点

### 1. Unity 主通信链已切到原生 WebSocket

`WebSocketClient.cs` 现在直接连接：

`ws://127.0.0.1:8766/ws`

并具备以下行为：

1. 先调用 `/api/health` 做 readiness 检查
2. 建立持久 WS 连接
3. 后台线程接收文本消息
4. 用线程安全队列回到 Unity 主线程再做 `MessageRouter.Dispatch()`
5. Unity 发送消息统一走同一条 WS 通道

### 2. 桥接主链已从 Unity 侧移除

已确认 `Assets/Scripts/Core/WebSocketClient.cs` 中不再保留：

1. `/api/ws` 发送主链
2. `/api/poll` 轮询主链
3. 旧的轮询循环逻辑

后端仍保留这些接口，仅作为兼容与调试入口，不再是 Unity 主路径。

### 3. 协议缺口已补齐

前端新增并接入：

1. `LOAD_COMPLETE`
2. `GAME_TIME_UPDATE`
3. `PLAYER_MOVE`

这样与后端 `runtime.py` 当前实际处理/发送的协议保持一致。

### 4. 启动卡死问题顺手修掉

这次切主链后，新增了一个直接相关的问题防护：

1. `WebSocketClient` 增加 `HasConnectAttemptFinished` / `LastConnectionError`
2. `GameManager.Start()` 不再只等待 `WS.IsConnected`
3. 如果健康检查通过但 WS 握手失败，会明确报错并中止启动，而不是一直卡在 `WaitUntil`

## 静态核对结果

### 已核对的后端协议源

来自 `backend/src/application/runtime.py`：

1. `SLEEP_TRIGGER`
2. `WAKE_UP`
3. `LOAD_COMPLETE`
4. `GAME_TIME_UPDATE`
5. `PLAYER_MOVE`

### 已核对的前端职责支点

来自 `Assets/Scripts/Data/SceneAnchorRegistry.cs`：

1. Unity 维护世界坐标 Anchor
2. `TryResolveNearestLocation()` 可把玩家世界坐标映射回 `location_id`

这说明当前“Python 只看语义位置，Unity 负责坐标落地”的职责拆分是通顺的。

## 验证方式

- [x] 读取并核对最新交接文档、最近执行记录、本轮方案文档
- [x] 静态核对 Unity 通信代码是否已切到 `/ws`
- [x] 静态核对后端 `runtime.py` 实际收发协议
- [x] 静态核对 `SceneAnchorRegistry` 与 `PlayerController` 的位置同步接口
- [ ] Unity Editor 编译验证
- [ ] Unity Play 模式联调验证

## 未完成项

1. 还没有在 Unity Editor 中实跑验证 `ClientWebSocket` 握手与消息分发
2. 还没有验证 `SLEEP_TRIGGER / WAKE_UP` 在 Play 模式下的画面联动
3. 还没有清理后端遗留的 `/api/ws`、`/api/poll` 兼容接口；这轮故意保留

## 补充说明

1. 当前工作区不是 git 仓库，无法用 `git diff / git status` 做版本校验
2. 项目使用 Unity 2022.3.62t7，静态上看本次使用的 `ClientWebSocket` / `Task` / `SemaphoreSlim` 语法与当前工程版本匹配
