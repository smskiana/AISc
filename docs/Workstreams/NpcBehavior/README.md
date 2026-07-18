# 工作流：NPC 行为

## 当前目标

让 NPC 从“随机移动 / 随机行动”收敛为“在对的时间、对的位置、做对的事情”。

本工作流关注行为语义，不替代导航系统。导航回答“能不能到”，NPC 行为回答“为什么去、去哪里、在那里做什么、做成没有”。

## 当前工程口径

1. 后端负责生成 NPC 行为意图，但地点和行为必须使用固定 ID。
2. 前端负责把行为意图落到场景、动画、气泡和物理位置。
3. `shared/actions.json`、`shared/locations.json` 和场景 `SceneAnchor` 应共同约束“哪些行为能在哪些地点发生”。
4. NPC 行为落地后应有结果语义：成功、失败、取消、超时。
5. 行为失败不能被当作已经完成，尤其不能提前更新 `NpcEntity.CurrentLocation`。
6. 会被 NPC 或玩家看见的重要行为，应能通过事件通道进入记忆系统。
7. 随机小行为不再由后端作为正式 `NPC_BEHAVIOR` 生成；前端只在空闲表现槽可用时播放可抢占的小动作或同区域踱步。
8. 玩家搭话时，前端可把当前空闲表现作为视觉上下文附给后端，但该上下文只用于当前对话开场，不等同于长期日程事实。
9. NPC 移动期间 `current_location` 使用唯一 transit 标记，并通过 `movement_origin / movement_target / movement_status` 保留移动语义；社交检测不得把 transit 当成任何地区。
10. 正式行为统一视为任务；`walk_to` / `run_to` 不再是 action，移动方式通过 `movement_mode` 独立表达。
11. 所有目标 location 不同的任务都由 Unity 执行“移动 -> 动作”状态机，导航到达不等于任务成功。
12. `succeeded / failed / cancelled` 只能由 Unity 运行时任务状态机裁决，并通过 `NPC_RUNTIME_EVENT` 非阻塞同步给后端；后端不再做阶段询问、停滞检测、重发或较长硬超时兜底。
13. NPC 的 P0 睡眠、need、energy、sociability、current_need 和 asleep 等运行时状态由 Unity 权威模块维护；Python 只能返回带 `base_world_revision` 的 `NpcStateEffect`，由 Unity 校验后应用或拒绝。
14. NPC-NPC 社交先由 Unity 完成双方真实移动，会合失败或超时不得生成对话或写入记忆。
15. NPC 行为与社交相关 LLM 调用不设置 `max_tokens` 硬上限；轮数、条目数、字数和 JSON 格式由 Prompt 软约束。
16. 开局和跨日的日计划必须通过 `BehaviorEngine.ensure_daily_plans(game_day, ...)` 准备；同一游戏日幂等，且供应商 LLM 调用不得阻塞 asyncio 协议事件循环。
17. 次日 `sociability_baseline` 只由 profile `social_base`、当日 `sociability_delta` 和玩家印象的受限 bias 计算；陈旧 NPC-NPC 基准不得参与全局平均。
18. 日计划、社交、玩家对话、世界准备和午夜维护只使用 Unity 请求携带的冻结 `GameTimeSnapshot`；Python 全局 `game_clock` 不再参与业务 operation。

## 当前问题

1. action-location-role 与 spot affordance 已进入共享配置和计划校验，但营业状态、精确时间窗和动态占用尚未接入。
2. 前端运行时已经按任务目标移动并执行动作，但场景 spot / anchor 仍需继续细化和 Play 验证。
3. 旧节点询问、停滞检测、硬超时和一次重发已删除；替代 spot 与按失败原因重新规划仍需另接 Unity 权威恢复策略。
4. 现有动作表现主要仍是颜色和等待时长，尚未接入各任务真实动画完成事件。
5. 空闲表现已从后端随机行为迁到前端，但仍需 Play 模式观察实际频率和踱步观感。
6. NPC-NPC 社交已接入 Unity 物理候选、后端纯语义意愿和 Unity 权威 session；Unity 在接受 decision 后原子 reservation、会合并请求内容，负责超时、播放、终态释放与冷却，仍需 Play 验证跨店会合和玩家抢占。
7. 玩家正常对话和 NPC-NPC 对话完成后都会广播 `NPC_SCHEDULE_REPLAN_CONTEXT`，Unity 再以权威剩余日程发送 `NPC_SCHEDULE_REPLAN_REQUEST`。
8. 日程 planner 已有单 owner 120 秒超时和确定性 fallback；仍需在真实供应商与 Play Mode 下复测批次长尾和迟到结果隔离。

## 已确认的日程优化口径

1. 移除日程语义输入中的固定字符截断，不再用 `[:420]`、`[:1800]`、`[:800]`、`[:600]` 等静默截断改变 LLM 实际可见信息。日程条目数量、合法枚举和业务时间范围仍属于领域约束，不等同于供应商 token 硬上限。
2. “互动后重规划”统一覆盖 NPC-NPC 社交和玩家正常对话；非正常取消、尚未产生有效对话内容的会话不触发。重规划必须接收稳定参与者 ID、互动类型、结束原因和已经生成的互动摘要，不能只传显示名。
3. 日计划候选应由结构化候选 DTO / 选择策略提供，不再把完整 action-location 笛卡尔结果拼成长字符串后从尾部截断。候选模块需要保证职业核心任务、固定 routine、当前地点附近任务、基本生存任务、社交任务和少量探索任务都有可见席位。
   - Prompt 输入统一使用紧凑标签格式表达 profile、计划上下文和候选，例如 `<action id="work_open" locations="flower_shop.doorway,..." />`；不为输入目录重复包装 JSON，也不切换到依赖缩进的 YAML。
   - 标签内容由 Prompt adapter 从结构化 DTO 渲染，业务模块和测试不得解析标签文本反推候选；稳定 ID、分组、优先级和来源继续保留在 DTO 中。
   - LLM 最终计划输出继续使用受控 JSON 数组，因为该结果需要严格解析、字段校验和 fallback；“输入改用标签”不等于把输出契约改成自由文本或 YAML。
4. 日计划生成与互动后重规划共用一个深模块和统一结果契约：计划生成、时间校验、affordance 校验、排序、冲突处理、fallback、失败原因和诊断由模块内部完成，调用方只提交上下文并接收已验证计划。
5. 每个 NPC 规划调用增加独立耗时、成功、fallback、超时和失败原因诊断；批次记录计划数、并发墙钟和最慢 owner。单请求长尾不得无限阻塞跨日，具体超时值在实施方案和真实供应商复测中确定。
6. 补齐时间语义校验：合法 `HH:MM`、单调排序、重复时间、清醒时段覆盖、错过步骤的处理策略，以及重规划步骤与旧剩余计划的去重 / 冲突合并。
7. 候选选择继续受 action-location-role affordance 约束，并逐步加入营业状态、时间窗、动态 spot 占用、天气和当前位置成本；LLM 只在合法候选中排序和组合，不负责创造新 ID。
8. 候选 DTO 和紧凑标签按外界因素分组，至少区分 `occupation / routine / need / relationship / weather / nearby / exploration`，并携带适用天气、营业状态、合法时间窗、位置成本、目标人物和来源理由。雨天优先室内与近距离候选，晴天开放公园、河边和跨店访问；关闭或不可用 spot 在进入 Prompt 前剔除。
9. 日计划设置傍晚社交窗口，目标为约 `16:30-18:30`，尽量让 NPC 在 `17:00` 左右结束或暂停职业任务，为相互拜访、散步、一起吃饭和偶遇留出时间。该窗口使用高权重软约束，不强制所有 NPC 同时离岗；应按店铺营业和角色职责错峰保留可接待者，避免“所有人都去拜访但没有人在店里”。
10. 傍晚窗口的计划校验至少保证：每名 NPC 有一个非工作候选席位；拜访者与接待者的时间窗相交；目标地点当时开放且可用；同一 NPC 不被安排为同时拜访和接待；没有合适社交对象时回退为散步、休息、吃饭或个人兴趣活动。
11. 日程候选使用确认的三层决策模型：第一层按世界物理情况做确定性合法性过滤；第二层以本地图路由和语义向量检索为候选补充长期记忆证据；第三层由单次 LLM 结合当天短期记忆、证据和已协调社交机会完成语义筛选与日程组合。日程保存 evidence ID、相似度、图路径分和 trace ID，不保存 embedding 向量本体。
12. 第二层不得因缺少记忆证据删除职业、routine、吃饭或休息等基础候选；关系、探索和个人兴趣候选可以按证据升降权或淘汰。第三层筛选与日程生成必须合并为每名 NPC 一次 LLM 调用，不得把每日调用数从 5 扩成 10。
13. Unity 持久化同游戏日未终态消费的剩余计划，并提供 `aisc_debug.daily_schedule_snapshot`；Unity 物理社交候选、运行时状态模块和 `NpcStateEffect` base revision 拒绝已接入，完整 Play Mode 长链仍需在编辑器稳定连接下复测。

## 下一阶段建议

1. 继续细化现有 action affordance：
   - 补营业状态、时间窗和动态 spot 占用。
   - 为真实动画 / 交互声明完成条件。
   - 增加失败原因到替代 spot / 重新规划的恢复策略。

2. 强化后端行为计划约束：
   - 不允许空 location。
   - 不允许 NPC 去不符合身份或营业状态的地点做动作。
   - 日常 routine 优先，LLM 只在允许候选中做选择或补理由。

3. 前端任务执行已拆分：
   - `NpcBehaviorApplier` 只做消息适配。
   - `NpcTaskExecutor` 负责任务阶段、移动、动作和终态。
   - 任务节点监督 reporter 已删除，终态只走 `NPC_RUNTIME_EVENT`。

4. 补行为恢复策略：
   - 后续补 Unity 权威替代 spot、按失败原因改计划和失败事件记忆策略。

5. 补 Play 模式诊断：
   - 记录 NPC 当前 action、目标 location、目标 spot、计划来源、执行结果。
   - 优先观察“去错地方”“到了不做事”“做事地点不合理”。

## 当前阶段排期

### 正在进行

1. Play 模式验证跨位置非移动任务的“移动 -> 动作 -> 成功”链。
2. 接入营业状态、时间窗和动态 spot 占用。
3. 补替代 spot 与按失败原因重新规划。
4. Play 模式观察长动作节点询问、结果丢包恢复和空闲表现观感。

### 正在计划

1. 更细的场景 spot / anchor 配置。
2. 真实动画 / 交互完成事件。
3. NPC 行为诊断面板或日志。

### 未来要做

1. 基于见闻和记忆的主动行为选择。
2. 店铺经营中顾客 / NPC 的语义化行为。
3. 送礼、交易、耕种、街机等玩法中的 NPC 参与行为。

## 暂缓事项

1. 不用“随机可达点”替代行为语义。
2. 不让 LLM 自由生成 Unity 不认识的地点或行为。
3. 不把行为解释继续堆进 `NpcSpawner`。
4. 不把动作 spot 缺失用运行时代码长期兜底。
5. 不把前端空闲表现写回后端行为状态或记忆系统。

## 相关设计与决策

1. `docs/DesignDocs/CodebaseBigPicture.md`
2. `docs/Workstreams/FrontendArchitecture/README.md`
3. `docs/Workstreams/Navigation/README.md`
4. `docs/DecisionRecords/ADR-0003-unity-mcp-asset-first.md`

## 专项草案

1. `ContextAwareDailyScheduleDraft.md`：外界感知候选、紧凑标签、傍晚社交协调、玩家 / NPC 互动后重规划、时间校验、fallback 与诊断的实施前设计来源。

## 相关执行证据

详见 `docs/AIChanges/NpcBehavior/README.md`。
