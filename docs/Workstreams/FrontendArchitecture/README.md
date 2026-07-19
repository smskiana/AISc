# 工作流：前端职责

## 当前目标

让 Unity 前端从能跑通的集中式脚本，逐步收敛为边界清楚的 Core / NPC / Navigation / Dialogue 分层。

## 当前工程口径

1. `GameManager` 暂时作为 facade，但不继续承接具体 UI 操作和协议细节。
2. `WebSocketClient` 负责连接和收发。
3. `MessageRouter` 负责消息 type 分发。
4. `NpcSpawner` 负责生成、注册、查找和事件订阅，行为消息应用由 `NpcBehaviorApplier` 承担。
5. `NpcBubbleManager` 负责气泡队列和轮播；`NpcSocialProtocolController` 负责社交协议终态；`NpcSocialRendezvousController` 负责距离判断和移动锁。
6. `PortraitDialogueUI` 当前可暂缓拆分，但新增状态前应先判断是否需要 view model 或子组件。
7. NPC 随机小行为由前端空闲表现层托管，作为可被后端行为、对话和社交锁抢占的表现资源。
8. NPC 行为执行结果由独立 reporter 职责回传，`GameStateStore` 不再在收到目标意图时提前更新位置。
9. `NpcBehaviorApplier` 保持薄适配，正式任务生命周期由 `NpcTaskExecutor` 承担；移动到达和动作完成是两个独立阶段。
10. 前端保留最近任务终态快照仅供 `aisc_debug` 诊断；后端节点询问、停滞检测、重发和硬超时已经删除。
11. NPC-NPC 社交由 Unity 回报物理 READY/FAILED 和播放 COMPLETE；后端不得用预计时间推断会合或已完成对话。

## 已完成阶段

1. 原生 WebSocket 联调。
2. 开始界面减重与资产化。
3. 前端托管后端生命周期。
4. 代码大局观文档。
5. 导航 typed path 第一阶段职责收口。
6. NPC 行为 request/result 闭环与玩家对话 PREPARED/READY 握手。
7. `GameCommandSender`、`GameStateStore`、`NpcBehaviorApplier`、`NpcSocialRendezvousController` 四项职责拆分。
8. NPC 空闲表现改由前端可抢占表现层托管。
9. NPC 统一任务执行器与 `NPC_RUNTIME_EVENT` 非阻塞终态接线；旧 `NPC_TASK_STATUS_QUERY / STATUS` 已删除。
10. 导航、协议、职责拆分与空闲表现的既有 Play 回归已完成。
11. 玩家传送 / 场景入口已按职责拆分为 `PlayerTeleportController`、`PlayerLocationResolver`、`PlayerTransitionView`，并通过 Unity MCP 完成 `Town_Main` 资产连线和 Play 验证。
12. 已新增项目专用 Unity MCP 工具 `aisc_debug`，以只读方式提供运行快照、健康报告、协议轨迹和 NPC 任务阶段，不把诊断聚合塞回 `GameManager`。
13. 暂停基础设施已区分 `Gameplay`、`UI`、`FX` 三个时间域；暂停来源由集中策略决定影响范围，`Time.timeScale` 只跟随 Gameplay 域。
14. 新游戏与午夜结算统一由世界准备流程锁定 `LoadingOverlay`；只有收到后端成功终态且目标游戏日 NPC 日计划已准备完成，才允许解除加载遮罩。

## 下一阶段建议

1. Play 模式持续验证 `NpcTaskExecutor`：跨位置任务、长动作终态、run 速度和 Unity 权威失败恢复重规划。
2. 评估拆 `DialogueSessionController`，承接玩家正式对话生命周期，避免继续加重 facade。
3. 在协议和存档底座稳定后，补玩家基础 UI，并严格按 MVC 切分 Model / View / Controller。
4. 新场景继续复用已完成的玩家传送职责和同一套 `NavigationTeleportPoint` / `SceneAnchor` 语义，不复制玩家专用入口数据。
5. 玩家插入 NPC 对话排在 NPC 见闻和主动搭话之后，不提前塞进现有对话 UI。
6. 继续观察 `NpcAmbientBehaviorController` 的空闲表现频率、同区域踱步路径和玩家搭话视觉上下文。
7. `aisc_debug` 保持只读；允许另设白名单式编辑器控制钩子，但工具和业务入口必须由 `UNITY_EDITOR` 条件编译保护，不得进入 Player 构建，也不得开放任意反射、任意字段写入或通用方法调用。
8. 新增暂停来源或动效消费者时，先查 `Assets/Scripts/Pause/README.md`；UI 动效不得依赖 Gameplay 的缩放时间，FX 资产必须通过 Unity MCP 接入受管适配器。

## 当前阶段排期

### 正在进行

1. NPC 新任务链 Play 验证：移动阶段、动作阶段、终态快照和失败/取消后的恢复重规划。
2. NPC affordance 第二阶段：营业时间、动态占用、替代 spot 和真实动作完成事件。
3. 配合 `ProtocolAndSave` 工作流实现 Unity 主存档、协议客户端和重连世界快照，不把协调职责塞回 `GameManager`。

### 正在计划

1. 玩家基础 UI，严格 MVC。
2. 玩家与 NPC 夜间回家睡觉、午夜结算、强制晕倒。
3. NPC 见闻、主动搭话、玩家插入 NPC 对话。
4. NPC 行为 spot / action affordance 细化。

### 未来要做

1. 店铺经营核心循环。
2. 送礼、交易、耕种、街机等玩法扩展。

## 暂缓事项

1. 不做一次性全前端大重构。
2. 不在业务修 bug 时顺手迁移所有历史类。
3. 不继续把新功能塞进已过重类。
4. 不在协议和存档底座稳定前推进复杂经营系统。

## 相关设计与决策

1. `docs/DesignDocs/CodebaseBigPicture.md`
2. `docs/AIChanges/FrontendArchitecture/2026-07-12_前端职责框架整改_plan.md`
3. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`
4. `docs/Workstreams/NpcBehavior/README.md`

## 专项执行方案

1. `PlayerBasicUIExecutionPlan.md`：玩家基础 UI、Unity 权威时间、睡眠跨日、存档管理与退出闭环的分阶段实施顺序和 Play 验收门槛。

## 相关执行证据

详见 `docs/AIChanges/FrontendArchitecture/README.md`。
