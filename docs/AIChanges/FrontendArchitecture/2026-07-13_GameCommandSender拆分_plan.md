> 执行记录: [2026-07-13_GameCommandSender拆分_execution.md](2026-07-13_GameCommandSender拆分_execution.md)

# GameCommandSender 拆分方案

## Workstream

FrontendArchitecture

## Roadmap item

FEA

## 相关 ADR

无新增 ADR；沿用当前前端职责工作流口径。

## 需求理解

按 Roadmap 的前端架构止血顺序，先拆 `GameCommandSender`，统一前端发给后端的命令构造。当前 `GameManager` 直接拼接 JSON 并调用 `WS.Send()`，后续协议 envelope、request_id、错误提示或本地发送前校验都会继续加重 `GameManager`。

## 方案思路

1. 新增 `Assets/Scripts/Core/GameCommandSender.cs`。
2. `GameCommandSender` 持有 `WebSocketClient`，负责构造并发送当前已有前端命令：
   - `GAME_START`
   - `DIALOGUE_START`
   - `DIALOGUE_END`
   - `PLAYER_CHOICE`
   - `FAST_FORWARD`
   - `PLAYER_MOVE`
   - `SAVE_REQUEST`
   - `LOAD_REQUEST`
   - `GET_SAVES`
3. 使用 `JsonUtility.ToJson()` 生成 JSON，替代 `GameManager` 手写字符串拼接。
4. `GameManager` 保留原有公开方法名，作为 facade 委托给 `GameCommandSender`，避免影响现有调用点。
5. 本轮不改变后端协议字段，不引入 envelope，不改存档 / 对话 / 玩家移动行为。

## 涉及文件

### 新增

1. `Assets/Scripts/Core/GameCommandSender.cs`
2. `docs/AIChanges/FrontendArchitecture/2026-07-13_GameCommandSender拆分_plan.md`
3. `docs/AIChanges/FrontendArchitecture/2026-07-13_GameCommandSender拆分_execution.md`

### 修改

1. `Assets/Scripts/Core/GameManager.cs`
2. `Assets/Scripts/Index.md`
3. `docs/AIChanges/ChangeIndex.md`

## 风险点

1. `JsonUtility` 只序列化字段，不序列化属性；命令 payload 使用 public field。
2. `GET_SAVES` 原本是无额外字段的 JSON，本轮保持只发送 `type`。
3. 公开 API 保持不变，降低对 UI、玩家控制器、对话 UI 的影响。

## 验证方式

1. `rg "WS.Send|SendGameStart|SendPlayerChoice" Assets/Scripts/Core Assets/Scripts/Dialogue` 检查调用。
2. `dotnet build AISc.sln --no-restore`。
3. Unity MCP 刷新脚本并校验 `GameCommandSender.cs` 与 `GameManager.cs`。
