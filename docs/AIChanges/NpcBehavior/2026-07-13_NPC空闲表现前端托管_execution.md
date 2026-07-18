> 设计方案: [2026-07-13_NPC空闲表现前端托管_plan.md](2026-07-13_NPC空闲表现前端托管_plan.md)

# NPC 空闲表现前端托管 — 执行记录

## 实际改动

| 文件 | 改动 |
|------|------|
| `backend/src/npc/behavior_engine.py` | 关闭后端 P6 随机微动作和随机需求生成；每 30 游戏分钟低频广播 `GAME_TIME_UPDATE`，供前端按游戏时间节流 |
| `backend/src/application/dialogue_service.py` | 接收 `DIALOGUE_START.visual_context`，作为当前对话开场系统提示注入，不作为长期日程或记忆事实 |
| `Assets/Scripts/Data/MessageTypes.cs` | 新增 `NpcVisualContext` 协议结构 |
| `Assets/Scripts/NPC/NpcAmbientBehaviorController.cs` | 新增前端空闲表现调度器，按游戏内 30 分钟尝试触发原地小动作或同区域踱步 |
| `Assets/Scripts/NPC/NpcEntity.cs` | 新增可抢占空闲表现槽、视觉上下文捕获、原地表现和同区域踱步入口 |
| `Assets/Scripts/NPC/NpcSpawner.cs` | 接入空闲表现调度器，转发时间同步并在后端行为到达时取消空闲表现 |
| `Assets/Scripts/Core/PlayerController.cs` | 玩家点击 NPC 搭话时捕获前端视觉上下文 |
| `Assets/Scripts/Core/GameManager.cs` | 对话开始流程透传视觉上下文 |
| `Assets/Scripts/Core/GameCommandSender.cs` | `DIALOGUE_START` 命令携带 `visual_context` |
| `Assembly-CSharp.csproj` | 补入新脚本编译项，保证当前工作区 `dotnet build` 可验证 |
| `Assets/Scripts/Index.md` | 补 `NpcAmbientBehaviorController` 索引 |
| `docs/Workstreams/NpcBehavior/README.md` | 回写“随机小行为前端空闲表现托管”口径 |
| `docs/Workstreams/FrontendArchitecture/README.md` | 回写前端空闲表现资源口径 |
| `docs/AIChanges/ChangeIndex.md` | 登记本轮计划与执行记录 |

## 行为口径

1. 后端不再把随机微动作作为正式 `NPC_BEHAVIOR` 发给 Unity。
2. 随机需求生成关闭，显式写入的 `current_need` 仍可由 P3 执行。
3. 前端空闲表现是可抢占资源：后端行为、玩家对话锁、NPC 气泡社交锁会取消它。
4. 同区域踱步调用 `MoveToLocation(CurrentLocation)`，复用现有 A* 候选点与可达性筛选，不直接随机坐标直线移动。
5. 玩家搭话时，前端把看到的空闲表现作为 `visual_context` 发给后端；后端只用于当前开场，不写为长期事实。

## 验证方式

1. `python -m py_compile backend/src/npc/behavior_engine.py backend/src/application/dialogue_service.py`
   - 结果：通过
2. `dotnet build Assembly-CSharp.csproj --no-restore`
   - 结果：通过
   - 备注：仍存在项目既有的程序集版本冲突警告和旧 JSON 字段未赋值警告，本轮未新增编译错误。

## 未完成项

1. 需要 Play 模式观察 30 游戏分钟触发频率是否符合实际观感。
2. 需要在 A* 场景里观察同区域踱步是否总能选到自然的可达点。
3. 后续若要增加更丰富的空闲表现，应继续只扩展前端空闲表现池，不回退到后端随机行为。
