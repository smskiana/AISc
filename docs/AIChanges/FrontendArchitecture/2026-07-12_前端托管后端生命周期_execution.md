> 设计方案: [2026-07-12_前端托管后端生命周期_plan.md](2026-07-12_前端托管后端生命周期_plan.md)

# 前端托管后端生命周期 — 执行记录

## 完成时间

2026-07-12

## 问题现象

1. Unity 前端启动开始界面时只检查 health，不会默认启动后端。
2. 点击启动后端后，`Process.Start()` 返回的 Python 进程没有被保存所有权，停止 Play / 关闭前端后后端会继续监听 `127.0.0.1:8766`。
3. 初版静态进程引用在 Unity 编辑器生命周期里不够稳，停止 Play 后曾出现 PID 3532 继续监听的情况。

## 根本原因

1. `StartMenuController.Start()` 调用的是 `BeginBootstrap(forceLaunch: false)`，所以默认只检查后端是否在线。
2. `StartMenuBackendLauncher.TryLaunchBackend()` 原先用 `using var process = Process.Start(...)`，进程对象立即释放，后续无法在前端退出时回收。
3. Unity 域重载 / 编辑器 Play 生命周期可能让静态字段丢失，因此仅保存 `_ownedBackendProcess` 不能覆盖所有退出路径。

## 实际改动

### `Assets/Scripts/Core/StartMenuController.cs`

1. 默认启动链改为 `BeginBootstrap(forceLaunch: true)`。
2. 新增 / 补充退出回收入口：
   - `OnDestroy()`
   - `OnApplicationQuit()`
3. 两个入口都调用 `StartMenuBackendLauncher.ShutdownOwnedBackend()`，该方法幂等，可重复调用。

### `Assets/Scripts/Core/StartMenuBackendLauncher.cs`

1. `TryLaunchBackend()` 不再用 `using` 立即释放进程对象。
2. 新增 owned 后端进程追踪：
   - `_ownedBackendProcess`
   - `TrackOwnedBackendProcess()`
   - `IsOwnedBackendRunning()`
3. 新增关闭方法：
   - `ShutdownOwnedBackend()`
4. 新增 `PlayerPrefs` 持久化 owned 进程信息：
   - PID
   - `Process.StartTime.Ticks`
5. 退出回收时通过 PID + 启动时间双重校验，只关闭本轮前端启动的 Python 后端，避免误杀用户手动启动的外部后端。

### 交接链

1. 新增本轮 plan / execution。
2. 新增 `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-12.md`。
3. 更新 `docs/ProjectIndex.md`，最新 handoff 指向 2026-07-12。

## 验证结果

### 1. C# 编译

命令：

```powershell
dotnet build AISc.sln --no-restore
```

结果：

- 0 error
- 8 warning

warning 均为既有 Unity 引用冲突 / 未赋值字段：

- `System.Net.Http` / `System.Security.Cryptography.Algorithms` / `System.IO.Compression` 版本冲突
- `LocationDatabase.LocationEntry` 等 JsonUtility 字段未显式赋值
- `GameManager._serverUrl` 已赋值未使用

### 2. Unity 编译

通过 Unity MCP 执行脚本刷新与编译等待：

- `refresh_unity(mode=if_dirty, scope=scripts, compile=request, wait_for_ready=true)`
- Console error：0

### 3. Play 模式启动验证

在 `127.0.0.1:8766` 无监听进程时进入 Play：

```text
[StartMenu] 已尝试启动后端: python "F:\GameProject\unity\AISc\backend\run.py" PID=2076
[WS] 健康检查通过: {...}
[WS] 已连接: ws://127.0.0.1:8766/ws
[WS] → {"type":"GET_SAVES"}
[WS] ← SAVES_LIST
```

说明：

- 前端已默认拉起后端。
- WS 连接和存档列表请求链路正常。

### 4. Play 模式停止验证

停止 Play 后检查：

```text
PID 2076 已退出
--- listening 8766 ---
```

说明：

- 本轮前端托管的后端进程已被回收。
- `8766` 无 `LISTENING` 进程残留。

## 未完成项

1. 没有验证打包后的独立 Windows Player 退出流程；当前已验证 Unity 编辑器 Play 模式。
2. 如果未来后端入口改为再派生独立服务进程，需要把关闭逻辑升级为进程树回收。

## 后续建议起点

1. 后续若继续做开始界面，可补“后端启动中 / 关闭中”的更细状态文案。
2. 若要支持玩家手动选择“保持后端运行”，可在开始界面增加一个显式开关；默认仍建议前端托管并退出回收。
