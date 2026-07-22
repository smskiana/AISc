# 项目路线图

## 作用

本文是项目运行方式的总入口之一，用来回答：

1. 当前项目按哪些长期目标推进。
2. 每个目标现在处于哪个阶段。
3. 哪些内容近期不做，避免反复重构。
4. 需要深入时应该进入哪个工作流索引。

本文不记录单次执行细节。执行证据统一回到 `docs/AIChanges/ChangeIndex.md` 和具体 `_plan.md` / `_execution.md`。

## 阅读方式

本文件只在任务涉及排期、长期目标或跨系统影响时读取。一般任务应从 `docs/ProjectIndex.md` 进入功能域，先读相关 Workstream 和代码目录 README；需要追溯实现原因时，再进入对应 `docs/AIChanges/<功能域>/`。不得按日期或最新 handoff 建立上下文。

## 当前路线图

| 编号 | 工作流 | 当前阶段 | 近期目标 | 入口 |
|------|--------|----------|----------|------|
| GOV | 项目治理 | 功能索引层已落地 | 维护功能 README、Workstream、ADR 与执行证据的一致性 | `docs/Workstreams/ProjectGovernance/README.md` |
| COG | 项目认知工具 | 核心原型可运行，实现未完成 | 补齐人工治理、关系证据查询与 VS Code 预览交互后再进入独立测试 | `docs/Workstreams/ProjectCognition/README.md` |
| MEM | 记忆系统 | v0.7 工程口径已收敛 | 保持轻量图 + 向量数据层，补诊断与质量评估，不扩张旧 v0.5 | `docs/Workstreams/Memory/README.md` |
| NAV | 导航系统 | typed path、移动结果、玩家传送与关键 Play 回归已完成 | 保持导航边界，后续承接 location candidate planner 与新场景入口配置 | `docs/Workstreams/Navigation/README.md` |
| NPC | NPC 行为 | 统一任务语义、affordance 与节点检测已落地 | Play 验证新任务链，补营业时间、动态占用与恢复策略 | `docs/Workstreams/NpcBehavior/README.md` |
| DIA | 对话系统 | 现场感知与准备握手已接入 | 做真实 LLM 长测，压缩 prompt，观察称呼与现场物件使用 | `docs/Workstreams/Dialogue/README.md` |
| FEA | 前端职责 | 第一阶段职责拆分与既有 Play 回归已完成 | 验证新增 NPC 任务执行器，继续约束 facade 与 UI 边界 | `docs/Workstreams/FrontendArchitecture/README.md` |
| PAS | 协议与存档 | 七批底座与 Play 回归已完成 | 保持协议和存档边界，后续玩法按现有 checkpoint 契约扩展 | `docs/Workstreams/ProtocolAndSave/README.md` |

## 三档排期

### 已完成底座

1. **前端职责第一阶段拆分**
   - `GameCommandSender` 统一前端命令构造与发送。
   - `GameStateStore` 承接时间、玩家位置、NPC 状态和对话状态写入。
   - `NpcBehaviorApplier` 从 `NpcSpawner` 拆出行为消息应用。
   - `NpcSocialRendezvousController` 从 `NpcBubbleManager` 拆出社交会合与移动锁。

2. **移动与协议第一阶段闭环**
   - `IMovementProvider` 已支持成功、失败、取消结果。
   - NPC 位置只在行为成功后提交，失败或取消不会提前写入目标地点。
   - `NPC_BEHAVIOR / NPC_ACTION_RESULT / ACK` 已接通 request 校验。
   - 玩家正式对话已接入 `PREPARED / READY` 握手，LLM 生成期间 WebSocket 保持监听。
   - NPC 移动期间使用唯一 transit 权威位置，不再归属出发地或目标地。

3. **随机行为与项目索引治理**
   - 后端不再生成随机正式微动作，前端空闲表现层托管可抢占的小动作和同区域踱步。
   - 项目索引、AIChanges 和目录 README 已改为按功能组织，不再按日期导航。

4. **导航、协议与前端 Play 回归**
   - 已验证跨店导航、移动成功 / 失败 / 取消、旧结果乱序和 transit 语义。
   - 已验证前端职责拆分、对话准备握手与空闲表现基础链路。
   - 后续 Play 工作只针对新增任务执行器和节点检测，不重新打开已完成的旧回归范围。

5. **NPC 正式任务语义底座**
   - 已建立 action-location-role affordance、全部 spot tags 和合法计划候选。
   - 已移除正式 `walk_to` / `run_to`，任务与移动方式分离。
   - 已完成 Unity 任务阶段执行、前端终态权威、结果丢包恢复和后端节点检测。

6. **协议与存档底座及 Play 回归**
   - 已实现并验证 Unity 权威世界存档、Python 记忆检查点与 `checkpoint_id` 双端提交。
   - 已完成真实保存、覆盖保存、读档、失败回滚和断线重连等 Play 回归。
   - envelope、协议版本、sequence、错误结构、握手和重连世界快照进入稳定维护状态。

7. **玩家传送 / 场景入口能力**
   - 玩家靠近现有 `NavigationTeleportPoint` 时显示“按 F 前往”，按 F 后移动到配对出口。
   - 玩家与 NPC 共享 `NavigationTeleportPoint`、`SceneAnchor` 和 `location_id`，但玩家不经过 NPC 自动寻路执行器。
   - 已拆分 `PlayerTeleportController`、`PlayerLocationResolver`、`PlayerTransitionView`，传送后立即同步玩家地点。
   - `Town_Main` 已复用现有 16 个传送端点完成 Play Mode 验证。

### 正在进行

当前优先处理“继续开发前必须止血”的底座问题。

1. **NPC 行为语义收敛：新增任务链验证与第二阶段约束**
   - 已建立 action-location-role affordance、spot tags 和合法计划候选。
   - 已移除正式 `walk_to` / `run_to`，移动方式改为任务参数。
   - 已完成前端“移动 -> 动作 -> 终态”执行器，以及后端阶段询问、停滞、硬超时和一次重发。
   - 下一步 Play 验证后补营业状态、时间窗、动态 spot 占用、替代 spot 和重新规划。

### 正在计划

这些内容排在架构止血、协议和存档底座之后，是下一批可执行功能。

1. **玩家基础 UI，严格 MVC**
   - 优先补时间 / 日期、当前地点、简单背包、存档读档、提示面板、设置入口。
   - Model 承接状态，View 只负责显示，Controller 处理输入并调用命令发送层。
   - 不把 UI 操作继续塞进 `GameManager`。

2. **夜间日常闭环**
   - 玩家主动睡觉。
   - NPC 到点回家睡觉。
   - NPC 回家失败处理。
   - 午夜结算。
   - 玩家超时强制睡眠 / 晕倒。
   - 晕倒后的地点、时间、状态和存档恢复。

3. **NPC 见闻与社交互动**
   - NPC-NPC 自发社交的物理会合、READY 后生成、播放 COMPLETE 后记忆提交已完成。
   - 前端判断 NPC 是否看见玩家行为，并通过玩家事件通道发给后端。
   - 后端将可记忆的玩家行动写入短期记忆，夜间自然入图。
   - NPC 主动搭话继续依赖玩家见闻、距离和状态；物理会合复用已完成的 NPC-NPC 社交协议。
   - 玩家插入 NPC 对话排在见闻与主动搭话之后。

4. **NPC 行为 affordance 第二阶段与资产细化**
   - 在现有 action-location-role 表上补营业状态、精确时间窗和动态 spot 占用。
   - 为柜台、货架、桌边、门口、收银台、河边等补更细 spot / anchor。
   - 将当前等待时长完成方式替换为真实动画 / 交互完成事件。
   - 补替代 spot、按失败原因重新规划和任务诊断面板。

5. **后端记忆优化：概率化节点融合**
   - 前置条件：前端正常流程、协议 / 存档底座和夜间主流程可以稳定跑完。
   - 将当前高相似度硬阈值融合，升级为“融合可能性 + 午夜概率抽签”。
   - 融合可能性同时考虑节点年龄、入边 clarity 平均值、向量相似度和旧记忆混淆压力。
   - 低相似度不设硬保护；特别旧且模糊的节点允许发生混淆式融合，但融合结果必须表达为模糊印象，避免生成确定新事实。
   - 保持 v0.7 轻量图口径，不扩成完整四阶段退化或全图 `similar_to` 网络。
   - 公式与实现计划见 `docs/Workstreams/Memory/README.md` 的“后续优化计划案：概率化节点融合”。

### 未来要做

这些是中长期玩法扩展，必须建立在前端架构、协议、存档、玩家传送和基础 UI 稳定之后。

1. **模拟经营店铺核心循环**
   - 前端负责店铺 UI、摆放 / 制作 / 售卖交互、顾客表现和结算界面。
   - 后端至少负责存档和关键经营事实记录。
   - 会影响 NPC 记忆 / 印象的经营事件，需要通过玩家事件通道进入后端。

2. **送礼系统**
   - 基于物品、关系、记忆和 UI 交互扩展。
   - 送礼结果应能影响 NPC 印象和后续对话。

3. **交易系统**
   - 基于物品、货币、库存和存档扩展。
   - 优先服务店铺经营，不单独做孤立经济系统。

4. **耕种系统**
   - 作为后续资源生产玩法，依赖物品、时间、存档和 UI 框架。

5. **街机系统**
   - 作为独立小游戏或店内互动扩展，后续单独立项。

## 当前冻结或暂缓事项

1. 不把旧 v0.5 记忆四阶段退化当作近期必须补齐项。
2. 不继续向 `AStarMovementProvider` 堆传送规则。
3. 不继续向 `GameManager` 增加具体 UI 操作。
4. 不通过运行时代码兜底 Unity 场景 / Prefab / SerializeField 资产层配置。
5. 不立即为项目文档补向量库；先用结构化索引解决管理问题。
6. 不在协议和存档底座稳定前推进复杂经营系统。
7. 不用“随机可达点”替代 NPC 行为语义。
8. 不重新引入 `walk_to` / `run_to` 作为正式 action；移动方式只能通过任务执行参数表达。
9. 后端不得根据预计时长推断任务成功；成功权威只来自 Unity 终态。

## 变更规则

非平凡实际实现修改应先判断它属于哪个路线图编号，并在本轮 plan / execution 顶部或正文中写明：

纯讨论、方案草案、排期安排和优先级调整不创建 plan / execution；需要落文档时直接更新 Roadmap、Workstream 或设计文档。

1. `Workstream`
2. `Roadmap item`
3. 相关 ADR
4. 相关设计文档
5. 本轮是否改变当前工程口径

如果本轮改变了工作流状态，应回写对应 `docs/Workstreams/*/README.md`。
