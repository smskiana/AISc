# 外界感知日程与互动后重规划草案

## 1. 文档定位

本文是 NPC 日程系统的实施前设计草案，记录已经确认的产品口径、模块职责、数据契约、流程、风险和验收方向。

本文不是实际实施 plan，不修改运行代码、配置、场景、Prefab 或资产连线。确认实施后，应在 `docs/AIChanges/NpcBehavior/` 创建唯一执行 plan，并在独立执行对话中完成。

主要功能域：NpcBehavior。

关联功能域：Memory、Dialogue、TestingAndDiagnostics、Navigation、FrontendArchitecture。

## 2. 背景与问题

当前每天为 5 名 NPC 各调用一次 `npc_daily_plan`。名义候选空间约为每人 21 种行为、330 个合法 action-location 组合，但实际 Prompt 存在以下问题：

1. `next_day_plan_context` 最终静默截到 420 字，内部近期记忆和印象也分别截断。
2. 任务候选、地点目录和行为目录分别静默截到 1800 / 800 / 600 字。
3. 约 6900 字的完整候选经过 1800 字截断后，通常只完整保留按字母排序的前 4-5 种行为，产生强烈选择偏置。
4. 5 名 NPC 独立生成计划，无法保证拜访者与接待者时间相交，也无法避免所有人同时离店。
5. 只有 NPC-NPC 社交完成会触发重规划；玩家正常对话不会改变剩余日程。
6. 当前只校验 action-location affordance，没有完整校验时间格式、排序、冲突、营业状态、天气、动态占用和错过步骤。
7. 正常日计划批次约 7-12 秒，但单个供应商请求缺少可诊断的长尾收口；历史出现过约 215 秒后才 fallback 的请求。

## 3. 已确认目标

1. 移除日程语义输入中的字符级静默截断，不再用字符串切片决定 LLM 能看到什么。
2. 先用本地规则按外界因素生成、过滤和协调结构化候选，再由 Prompt adapter 渲染为紧凑标签。
3. 外界因素至少包含天气、营业状态、合法时间窗、当前位置与路程、动态 spot 占用、人物关系和当日记忆摘要。
4. 约 `16:30-18:30` 设置傍晚社交窗口，尽量让 NPC 在 `17:00` 左右退出职业任务，为拜访、接待、散步、聚餐和偶遇留下空间。
5. 傍晚窗口使用高权重软约束，不强迫所有 NPC 同时离岗；店铺与角色职责需要错峰保留接待者。
6. NPC-NPC 社交和玩家正常对话都进入统一的互动后重规划流程。
7. LLM 输入使用紧凑标签，最终计划输出继续使用受控 JSON，供严格解析和校验。
8. 日计划生成、重规划、校验、fallback 和诊断收敛为一个深模块，`BehaviorEngine` 不再自行拼 Prompt 和处理所有分支。
9. 日程候选采用已确认的三层决策模型：世界物理可行性过滤、图与向量记忆证据增强、单次 LLM 基于当天短期记忆完成语义筛选和日程组合。

## 4. 非目标

1. 不让 LLM 生成新的 action ID、location ID、NPC ID 或营业规则。
2. 不让 LLM 直接决定场景 spot 是否存在或是否可用。
3. 不在本轮引入完整 GOAP、行为树或通用约束求解基础设施。
4. 不把全部 330 个组合换一种文本格式后原样塞入 Prompt。
5. 不把最终计划输出改成自由文本或 YAML。
6. 不为实现日程逻辑修改 Unity 场景、Prefab、SerializeField 或 UI 资产；若实施发现资产层需求，必须另按 Unity MCP 规则处理。

## 5. 领域术语

### 5.1 DailySchedule

某名 NPC 在一个游戏日内按时间排序的已验证任务集合。

### 5.2 ScheduleCandidate

本地系统已经确认 action、location、NPC 身份、时间窗和外界条件合法的一条可选任务。LLM 只能选择、排序或组合候选，不能创造候选之外的稳定 ID。

### 5.3 CandidateGroup

候选的语义来源，稳定值为：

- `occupation`
- `routine`
- `need`
- `relationship`
- `weather`
- `nearby`
- `exploration`

同一候选可以属于多个 group，但必须保留一个 `primary_group` 供诊断和覆盖校验。

### 5.4 SocialOpportunity

两名人物在重叠时间窗和合法地点上形成的可执行社交机会，包含 `visitor / host / peer` 角色、目标人物、地点、时间窗和来源关系。

### 5.5 EveningSocialWindow

默认约 `16:30-18:30` 的高权重软窗口。目标不是强制社交，而是避免职业任务占满傍晚，并为可协调的社交活动预留至少一个席位。

### 5.6 InteractionReplan

一次有效 NPC-NPC 社交或玩家对话结束后，对单名 NPC 剩余日程进行的局部更新。它不重做已完成任务，也不改变其他 NPC 已锁定且未受影响的计划。

## 6. 模块与 seam

新增一个日程深模块，建议文件入口：

- `backend/src/npc/daily_schedule.py`
- `backend/src/npc/schedule_candidates.py`
- `backend/src/npc/schedule_memory_evidence.py`
- `backend/src/npc/schedule_prompt_adapter.py`
- `backend/src/npc/schedule_diagnostics.py`

公开 seam 只保留两个主要接口：

```python
class DailySchedulePlanner:
    async def prepare_day(
        self,
        request: DailyScheduleBatchRequest,
    ) -> DailyScheduleBatchResult:
        ...

    async def replan_after_interaction(
        self,
        request: InteractionReplanRequest,
    ) -> NpcScheduleResult:
        ...
```

`prepare_day()` 在内部完成：

1. 读取世界与 NPC 快照。
2. 构建结构化候选。
3. 协调跨 NPC 社交机会。
4. 渲染紧凑标签。
5. 有界并发调用 LLM。
6. 解析和校验计划。
7. 处理冲突与 fallback。
8. 返回批次结果和诊断。

`replan_after_interaction()` 在内部完成：

1. 判断互动是否有效且允许重规划。
2. 冻结当前时间、当前任务和剩余计划。
3. 合并互动摘要、关系变化和外界状态。
4. 只生成当前时间之后的候选。
5. 校验、去重并与旧剩余计划合并。
6. 返回新计划和可诊断结果。

`BehaviorEngine` 只负责调用这两个 seam、保存已验证计划并按优先级执行，不再直接构造 Prompt 或解析 LLM JSON。

## 7. 输入 DTO

### 7.1 DailyScheduleBatchRequest

```python
@dataclass(frozen=True)
class DailyScheduleBatchRequest:
    game_day: int
    game_time: str
    weather: str
    npc_snapshots: tuple[NpcScheduleSnapshot, ...]
    business_windows: tuple[BusinessWindow, ...]
    spot_availability: tuple[SpotAvailability, ...]
    evening_social_window: TimeWindow
```

### 7.2 NpcScheduleSnapshot

```python
@dataclass(frozen=True)
class NpcScheduleSnapshot:
    npc_id: str
    current_location_id: str
    home_location_id: str
    occupation: str
    profile_tags: tuple[str, ...]
    routines: tuple[RoutineEntry, ...]
    plan_context: ScheduleContext
    relationship_opportunities: tuple[RelationshipOpportunity, ...]
```

### 7.3 ScheduleContext

`ScheduleContext` 保持结构化字段，不预先压成 420 字字符串：

```python
@dataclass(frozen=True)
class ScheduleContext:
    lingering_concern: str
    recent_events: tuple[ScheduleEventSummary, ...]
    relationship_states: tuple[ScheduleRelationshipState, ...]
    current_need: str
```

不允许用 `[:N]` 静默截断字段。若候选或上下文规模过大，必须通过有业务含义的选择规则收口，并在诊断中记录 `selected / omitted` 及理由。

### 7.4 ScheduleCandidate

```python
@dataclass(frozen=True)
class ScheduleCandidate:
    candidate_id: str
    action_id: str
    location_id: str
    primary_group: str
    groups: tuple[str, ...]
    valid_windows: tuple[TimeWindow, ...]
    weather_ids: tuple[str, ...]
    business_state: str
    travel_cost: float
    target_person_id: str = ""
    social_role: str = ""
    source_reason: str = ""
    memory_evidence: tuple[ScheduleMemoryEvidence, ...] = ()
    memory_relevance_score: float = 0.0
```

`candidate_id` 使用稳定 `snake_case`，只在本次规划请求内标识候选，不进入共享存档主键。

### 7.5 ScheduleMemoryEvidence

```python
@dataclass(frozen=True)
class ScheduleMemoryEvidence:
    memory_node_id: str
    evidence_type: str
    vector_similarity: float
    graph_path_score: float
    retrieval_trace_id: str
```

`evidence_type` 使用稳定枚举，例如：

- `recent_interaction`
- `relationship`
- `shared_event`
- `place_interest`
- `personal_interest`
- `emotional_avoidance`

日程只保存证据 ID、类型和评分，不保存 embedding 向量本体，也不把向量数值当作事实。

## 8. 三层决策模型

### 8.1 第一层：世界物理可行性过滤

先复用 `NpcTaskCatalog` 过滤：

1. action 存在。
2. location 存在。
3. NPC 身份允许。
4. action-location affordance 匹配。

外界因素继续执行确定性过滤：

在基础合法性上增加：

1. `weather`：雨天关闭不适合的室外长活动，优先室内和近距离候选；晴天开放公园、河边和跨店访问。
2. `business_window`：职业任务只能进入合法营业 / 准备 / 收尾时间窗；关闭店铺不能作为普通顾客活动地点。
3. `spot_availability`：已占用、关闭或缺失 spot 在进入 Prompt 前剔除。
4. `travel_cost`：使用导航或地点邻接的估算成本，避免短时间窗内安排不可能完成的跨区移动。
5. `relationship`：只为当前关系、印象、近期互动或明确 routine 支持的人物生成拜访候选。
6. `need`：吃饭、休息等基础需求必须保留合法候选，不被社交或探索完全挤掉。

第一层可以真正删除候选，因为它回答的是“当前世界中能不能执行”。每个删除动作必须记录稳定原因，例如 `weather_forbidden / business_closed / spot_unavailable / travel_time_exceeded / affordance_invalid`。

### 8.2 第二层：图与向量记忆证据增强

第二层由 `ScheduleMemoryEvidenceProvider` 提供本地记忆 seam：

```python
class ScheduleMemoryEvidenceProvider:
    def enrich(
        self,
        request: ScheduleEvidenceRequest,
    ) -> ScheduleEvidenceResult:
        ...
```

执行原则：

1. 每名 NPC 使用本地确定性方向，不调用 `memory_direction`。
2. 向量检索寻找与候选 group、人物、地点和活动语义相关的记忆锚点。
3. 轻量图路由从锚点扩展人物关系、共同事件、地点兴趣、情绪和印象依据。
4. 检索结果给候选增加 `memory_evidence` 和 `memory_relevance_score`，不直接把重建后的长文本塞给所有候选。
5. 证据必须保留 `memory_node_id / retrieval_trace_id / vector_similarity / graph_path_score / evidence_type`。
6. 不对 330 个候选逐条发起检索；应按 NPC 和语义 group 批量构造少量 query，并让同一证据复用到相关候选。
7. 5 名 NPC 的证据增强可以有界并发，不增加供应商 LLM 调用。

记忆证据的筛选权限分级：

1. `occupation / routine / need`：没有记忆证据不能删除，只能影响同类候选内部排序。
2. `relationship / exploration / personal_interest`：允许根据正向、负向或缺失证据升权、降权或淘汰。
3. 剧情和系统强制候选：不受普通记忆证据删除，只记录记忆是否支持。
4. 明确负面证据可以降低拜访倾向，但不能绕过物理合法性和剧情规则。

第二层回答的是“为什么今天更可能做”，不是再次判断物理合法性。

### 8.3 跨 NPC 社交机会协调

完成记忆证据增强后，再根据双方关系证据、物理时间窗和地点条件构造 `SocialOpportunity`。这样 17:00 左右的 visitor / host / peer 配对同时具备可执行性和记忆动机。

### 8.4 第三层：单次 LLM 语义筛选与日程组合

每名 NPC 只进行一次 `npc_daily_plan` LLM 调用。不得先调用一次“筛选 LLM”，再调用第二次“日程生成 LLM”。

第三层输入：

1. 第一层保留的物理合法候选。
2. 第二层生成的图 / 向量证据。
3. 当天短期记忆原文或结构化摘要。
4. 心事、即时状态和玩家 / NPC 关系变化。
5. 已协调的傍晚社交机会。
6. 天气、营业窗口和当前位置。

第三层负责：

1. 在合法候选中做语义筛选。
2. 根据当天短期记忆判断当天连续性。
3. 使用长期图 / 向量证据解释个性化和社交选择。
4. 组合时间顺序和日程节奏。
5. 为被选计划项返回实际使用的 `evidence_ids`。

LLM 不能引用本次请求之外的证据 ID。本地收口必须验证 `candidate_id` 和 `evidence_ids` 都属于本次输入。

### 8.5 类别覆盖

不使用按字符串长度截断。候选选择必须保证：

1. 职业核心任务可见。
2. profile routine 可见。
3. 基础需求候选可见。
4. 当前地点或邻近区域候选可见。
5. 至少一个个性化或探索候选可见。
6. 存在合法关系机会时，傍晚社交候选可见。

如果候选仍过多，按相关性、时间可执行性和类别覆盖选择，并记录淘汰原因。禁止从渲染后的字符串尾部截断。

## 9. 傍晚社交协调

5 名 NPC 独立调用 LLM 前，先由本地协调器构建 `SocialOpportunity`。

### 9.1 时间窗口

默认目标窗口：

```text
16:30-18:30
```

期望行为：

1. 尽量在 17:00 左右停止、暂停或收尾职业任务。
2. 每名 NPC 至少获得一个非工作候选席位。
3. 有合适关系对象时优先形成可配对的拜访、接待、散步、聚餐或偶遇机会。
4. 没有合适对象时保留个人兴趣、吃饭、休息或散步。

### 9.2 访客与接待者

拜访必须满足：

1. visitor 与 host 的时间窗相交。
2. host 在该时段位于可接待地点，或双方约在中立地点。
3. 地点营业 / 开放且 spot 可用。
4. visitor 的路程能在窗口内完成。
5. 同一 NPC 不同时承担冲突的 visitor / host 任务。

### 9.3 错峰

不能让所有 NPC 同时离店。协调器应根据职业和营业规则形成错峰，例如：

```text
16:30-17:20  千早留店收尾并可接待
16:40-17:20  樱拜访千早
17:20-18:00  千早离店，与一叶在街区散步
17:00-18:00  龙之介留店或在中立地点参加聚餐
```

这只是语义示例，实际人物和地点必须由当日关系、营业状态和候选决定。

### 9.4 玩家机会

玩家没有固定自动日程，但 NPC 可以获得面向玩家的机会候选：

- `visit_player_cafe`
- `wait_near_player_route`
- `invite_player`
- `mention_recent_player_interaction`

只有项目中已有对应正式 action 和协议能力时才能进入执行计划；否则只能保留为后续设计，不得用未知 action 兜底。

## 10. 紧凑标签 Prompt

### 10.1 输入格式

Prompt adapter 从 DTO 单向渲染标签，业务模块不解析标签反推数据。

```text
<schedule npc="sakura" day="5" weather="rainy">
  <context>
    <concern>担心花店明天的客流</concern>
    <event>今天和玩家聊到春季花束</event>
  </context>

  <window id="evening_social" time="16:30-18:30" weight="high" />

  <candidates group="occupation">
    <task ref="sakura_work_open_flower_shop_doorway"
          action="work_open"
          location="flower_shop.doorway"
          time="08:00-09:00" />
  </candidates>

  <candidates group="relationship">
    <task ref="sakura_visit_chihaya_bakery"
          action="visit"
          location="bakery.doorway"
          target="chihaya"
          role="visitor"
          time="16:40-17:20"
          travel="low"
          memory_score="0.82"
          evidence="memory_123,memory_456" />
  </candidates>

  <short_term_memory>
    <event id="stm_789">今天和千早约好傍晚去看看新面包</event>
  </short_term_memory>
</schedule>
```

### 10.2 输出格式

LLM 最终输出继续使用 JSON 数组，并优先引用 `candidate_id`：

```json
[
  {
    "time": "08:10",
    "candidate_id": "sakura_work_open_flower_shop_doorway"
  },
  {
    "time": "16:40",
    "candidate_id": "sakura_visit_chihaya_bakery",
    "evidence_ids": ["memory_123", "memory_456", "stm_789"]
  }
]
```

本地根据 `candidate_id` 恢复 action、location、target 和来源，并验证 `evidence_ids` 来自本次图 / 向量检索或短期记忆输入。为了兼容旧契约，迁移阶段可以同时接受旧 `action / location`，但正式收口后只保留一种输出契约。

### 10.3 关于上限

1. 不设置供应商 `max_tokens` 硬上限。
2. 不使用字符切片截断输入。
3. “每天安排若干任务”“时间范围必须合法”等仍是领域约束。
4. 候选规模通过结构化筛选和类别覆盖降低，不通过截断渲染结果降低。

## 11. 时间与计划校验

计划收口必须验证：

1. `time` 是合法 `HH:MM`。
2. 时间位于 NPC 清醒范围。
3. 计划按时间单调排序。
4. 同一 NPC 没有重叠或重复任务。
5. `candidate_id` 属于本次请求且归属当前 NPC。
6. action-location affordance 在提交时仍合法。
7. 任务时间落在候选合法窗口内。
8. 职业任务不侵占已经协调的傍晚社交机会，除非当日营业规则明确要求。
9. 拜访与接待配对仍然成立；失配时双方都不得保留不可执行的半边任务。
10. 计划存在合理的职业、需求、休息和个性活动分布。

LLM 结果部分非法时，不应简单保留任意一条合法步骤后结束。应先移除非法步骤，再用候选和 routine 补齐关键时段，形成完整可执行计划。

## 12. 错过步骤与执行语义

当前 `±1` 分钟匹配会让被高优先级行为打断的计划永久错过。新逻辑应明确：

1. `fixed`：营业开门、约定拜访等固定任务；短暂错过后在宽限窗口内补执行，超时则显式取消或重规划。
2. `flexible`：散步、看书、休息等；可在合法窗口内顺延。
3. `opportunistic`：偶遇、短暂社交；条件消失后直接跳过。

每个计划项应携带 `timing_mode`、`valid_window` 和 `miss_policy`，而不是只保存一个时间点。

## 13. 互动后重规划

### 13.1 触发条件

触发：

1. NPC-NPC 社交正常完成。
2. 玩家对话以 `player_left / completed / normal` 结束，且至少产生一条有效 NPC 回复。

不触发：

1. 准备阶段取消。
2. 没有有效对白内容。
3. 睡眠、断线或致命错误导致的异常结束。
4. 当前没有剩余计划且已接近睡眠时间。

### 13.2 InteractionReplanRequest

```python
@dataclass(frozen=True)
class InteractionReplanRequest:
    npc_id: str
    participant_id: str
    interaction_type: str
    end_reason: str
    game_time: str
    location_id: str
    interaction_summary: str
    relationship_delta: float
    current_task: ScheduledTask | None
    remaining_schedule: tuple[ScheduledTask, ...]
    world_snapshot: ScheduleWorldSnapshot
```

`interaction_type` 使用稳定值：

- `player_dialogue`
- `npc_dialogue`

### 13.3 合并规则

1. 已完成计划不重写。
2. 当前不可中断任务不被重规划替换。
3. 新步骤只能安排在当前时间之后。
4. 新步骤和旧剩余步骤按候选 ID、时间窗和目标人物去重。
5. 玩家对话可能提高或降低后续拜访、独处、散步、工作投入等候选权重，但不能直接创造未实现玩法。
6. NPC-NPC 社交影响双方，但双方分别生成并校验；若涉及新的双人任务，必须重新通过 `SocialOpportunity` 协调。

## 14. Fallback

Fallback 不是简单复制 profile routines，而是使用同一候选 DTO 构建确定性计划：

1. 先放入必须职业任务。
2. 放入基础需求与休息。
3. 放入合法 routine。
4. 在傍晚插入已协调社交机会；没有机会则放入个人活动。
5. 用附近、低成本候选补足明显空白时段。
6. 经过与 LLM 结果相同的最终校验。

供应商异常、超时、解析失败、全部候选拒绝和跨 NPC 社交失配必须使用稳定失败原因，不得只写日志。

## 15. 性能与并发

1. 5 名 NPC 继续有界并发规划，批次墙钟应接近最慢 owner，而不是 5 次之和。
2. 候选构建、外界过滤和社交协调必须是本地确定性阶段，不增加 LLM 调用。
3. 每名 NPC 正常每天最多一次完整日计划调用；同一日幂等。
4. 玩家或 NPC 互动后只重规划受影响 NPC；双人新社交任务需要协调时才更新另一方。
5. 单个供应商长尾不得无限阻塞跨日；实施 plan 必须基于真实供应商数据确定超时和 fallback 策略。
6. 紧凑标签应减少重复文本，但不得再引入字符截断。性能收益通过字符数、供应商耗时和选择质量共同验证。
7. 第二层按 NPC / group 批量检索并复用证据，不允许对每个 action-location 组合分别执行 embedding 和图路由。
8. 第三层筛选与计划生成合并为现有的一次 LLM 调用，三层模型不得把日计划调用数从 5 增加到 10。

## 16. 诊断同步

### 16.1 后端诊断

新增日程批次与单 NPC 结构化快照：

1. operation ID、game day、阶段和状态。
2. 天气、营业状态版本、spot 可用性版本。
3. 原始合法候选数、各 group 候选数、入选数和淘汰理由。
4. 傍晚社交机会、visitor / host / peer、配对状态和冲突原因。
5. 每 owner LLM 耗时、成功、fallback、超时和失败原因。
6. 计划校验错误、补齐步骤和最终条目数。
7. 批次并发墙钟、最慢 owner 和总耗时。
8. 互动后重规划的 participant ID、interaction type、保留 / 替换 / 新增 / 删除计数。
9. 三层各自记录输入数、保留数、拒绝数和原因；第二层记录 query 数、向量命中、图路径、证据复用数和无证据候选数。
10. 最终计划项记录实际采用的 candidate ID、evidence IDs 和关联 retrieval trace ID，不暴露原始 embedding。

### 16.2 Unity 诊断

`aisc_debug` 应增加或扩展：

- `daily_schedule_snapshot`
- `interaction_replan_snapshot`

快照只返回稳定 ID、分类、时间窗、状态、计数和失败原因，不暴露完整 Prompt 或原始 LLM 输出。

如需要可重复验证，`aisc_control` 可以增加编辑器专用白名单日程探针，但探针必须使用正式 planner seam，并明确只读或隔离写入范围。

## 17. 测试先行的 seam

优先围绕 `DailySchedulePlanner` 两个公开 seam 写测试，不直接断言内部私有函数。

### 17.1 候选测试

1. 雨天剔除不适合的室外长活动，保留室内候选。
2. 晴天开放公园、河边和跨店访问。
3. 关闭店铺不能作为普通访问地点。
4. 被占用或缺失 spot 不进入候选。
5. 职业、routine、need、nearby、relationship、exploration 保持类别覆盖。
6. 候选数量增长时不发生字符串截断或字母排序偏置。
7. 无记忆的新 NPC 仍保留 occupation、routine 和 need 候选。
8. relationship / exploration 候选能被相关记忆升权，被明确负面记忆降权。
9. 多个同组候选复用批量检索证据，不发生逐候选检索。

### 17.2 傍晚社交测试

1. 17:00 左右每名 NPC 至少有一个非工作候选席位。
2. visitor / host 时间窗相交且地点开放。
3. 不出现所有 NPC 同时离店。
4. 同一 NPC 不同时承担冲突角色。
5. 没有合适对象时回退个人活动。
6. 雨天社交迁移到合法室内或近距离地点。

### 17.3 计划校验测试

1. 非法时间、乱序、重复和冲突被明确拒绝或修复。
2. 未知 candidate ID 被拒绝。
3. 部分非法输出能用本地候选补齐完整计划。
4. `fixed / flexible / opportunistic` 的错过策略符合语义。
5. 跨 NPC 社交半边失配时双方计划保持可执行。

### 17.4 重规划测试

1. 玩家正常对话触发单 NPC 重规划。
2. NPC-NPC 社交触发双方重规划。
3. 异常结束和空对话不触发。
4. 已完成计划和不可中断当前任务保持不变。
5. 新旧计划合并不重复、不回到过去时间。
6. 对话影响只调整合法候选权重，不创造未知玩法。

### 17.5 性能测试

1. 5 名 NPC 调用实际并发。
2. 单 owner 长尾被稳定收口并 fallback。
3. 批次诊断能指出最慢 owner。
4. 紧凑标签相对现有重复目录明显减少输入，但候选覆盖率不下降。
5. 完整跨日墙钟同时包含午夜记忆和日计划阶段，不再只报告其中一段。
6. 三层模型仍保持每名 NPC 一次日计划 LLM 调用。
7. 第二层本地证据增强的墙钟和 query 数有独立上限与诊断，不能悄悄成为新瓶颈。

## 18. 验收标准

1. 日程 Prompt 不再出现 `[:420] / [:1800] / [:800] / [:600]` 静默截断。
2. LLM 实际可见候选由结构化选择决定，诊断可解释每类候选为何入选或淘汰。
3. 天气、营业状态、时间窗、当前位置成本和 spot 可用性实际影响候选。
4. 17:00 左右形成可执行的非工作窗口，并至少在存在关系机会时形成合法 visitor / host 或 peer 配对。
5. 不出现所有 NPC 同时离店、无人接待或双人任务只有半边的计划。
6. 玩家正常对话和 NPC-NPC 社交都能触发统一重规划。
7. 非法 LLM 输出不能进入执行层；fallback 计划同样通过完整校验。
8. 日计划和重规划拥有结构化诊断、稳定失败原因和关联 ID。
9. 正常批次性能不回退，供应商长尾不会无限阻塞跨日。
10. 后端定向测试、完整测试、Unity EditMode 诊断测试和隔离 Play Mode 跨日验证通过。
11. 每个个性化 / 社交计划项能追溯到合法 candidate ID 和实际输入的短期记忆或图 / 向量 evidence ID；不存在伪造 evidence ID。
12. occupation、routine 和 need 不因缺少记忆证据被删除；relationship、exploration 和 personal_interest 按证据进行可解释升降权。

## 19. 风险与待确认项

1. 营业时间和动态 spot 占用目前可能缺少完整共享配置；实施前需确认数据来源，不能让 planner 猜测。
2. 关系机会过度加权可能让 NPC 每天重复拜访同一对象，需要冷却和近期重复惩罚。
3. 17:00 社交窗口是高权重软约束；节日、紧急事件、职业职责和剧情任务应允许覆盖。
4. 玩家相关候选受当前正式 action 和协议能力限制，不能把叙事意图直接当作已实现行为。
5. 日计划条目是否继续使用“至少 4、最多 8”的软要求，需要在实施 plan 中结合完整清醒时段和任务持续时间确认。
6. 单 owner 供应商超时值尚未确认，应使用真实供应商多轮数据决定，不在草案中拍固定数字。
7. 如果跨 NPC 社交协调演变成通用资源占用与多人约束求解，应先评估是否需要独立的调度模块或新 ADR，不能继续堆入 `BehaviorEngine`。

## 20. 建议实施顺序

1. 建立 DTO、候选模块和 planner seam，补纯函数测试。
2. 移除字符截断，迁移紧凑标签 Prompt adapter 和 candidate ID 输出。
3. 补时间校验、完整 fallback 和错过步骤语义。
4. 接入天气、营业时间、位置成本和 spot 可用性。
5. 实现傍晚社交机会协调与错峰。
6. 将 NPC-NPC 社交和玩家对话统一接入互动后重规划。
7. 同步后端 / Unity 诊断与控制钩子。
8. 使用隔离数据完成真实 LLM、完整跨日和 Play Mode 验证。
