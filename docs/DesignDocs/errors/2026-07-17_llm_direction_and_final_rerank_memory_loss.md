# 2026-07-17：LLM 方向合法误判与最终重排丢失实体记忆

## 错误现象

玩家询问“你知道千早在哪里吗，我在找她”时，Unity 对话流程、后端连接和 LLM 请求均成功，但樱的回答没有稳定使用千早相关记忆。

实际检索 trace：

- `retrieval_16d9cdaa8306`
- `retrieval_b0196cc904c0`

方向诊断显示：

```json
{
  "entity_mentions": ["千早"],
  "location_mentions": ["flower_shop.counter"],
  "themes": ["general"],
  "relation_facets": [],
  "time_scope": "recent",
  "recall_intent": "general_recall",
  "negative_directions": []
}
```

其中“千早”识别正确，但“在哪里”没有被识别为 `locate_person` / `current_location`；`flower_shop.counter` 是当前对话地点，不是问题中的目标地点。

图搜索随后已经命中千早相关节点和边，但最终上下文只保留了 5 个节点，千早相关记忆被玩家背景和其他事件节点挤掉。

## 根本原因

### 1. LLM 输出格式正确但语义错误

`memory_direction` 只要求返回合法 JSON 和白名单枚举。LLM 返回 `general_recall` 属于结构合法结果，当前解析层没有对“在哪 / 哪里 / 位置 / 当前在哪里”等明确定位词执行确定性语义校正，也没有在 LLM 方向与本地方向明显冲突时选择本地方向。

### 2. 本地最终重排对节点类型的先验过强

最终重排对 `event` 节点增加固定类型分，对 `person` / `identity` 节点没有对应的实体命中保护。结果是：路径阶段已经命中的“千早”记忆，在最终 `final_memory_limit` 截断前被无关事件节点超过。

这比方向误判更直接地造成“想不起千早”：即使图搜索已经找到了目标实体，最终提供给对白 LLM 的记忆上下文仍然没有目标实体。

## 边界确认

“千早当前在哪里”本轮测试不要求把实时 `npc_states.current_location` 注入樱的记忆检索，也不要求 NPC 得到绝对正确的实时位置。

允许 LLM 基于记忆进行非原则性推断或犯错；不允许因检索丢失目标实体而表现为完全想不起千早。防编造测试的关键是：对白 LLM 只能基于最终保留下来的记忆证据回答，缺少证据时应保持不确定，而不是补造确定事实。

## 正确做法

1. 在 LLM 方向结果收口处增加独立的确定性规则校准 seam：明确定位问句至少校正为 `locate_person` 与 `current_location`，并保留校准动作的诊断证据。
2. 最终重排增加查询实体命中和路径实体证据的优先级；类型先验只能作为次级排序因素，不能挤掉明确命中的人物 / 身份记忆。
3. 诊断中同时区分：LLM 原始方向、校准后的方向、图搜索命中节点和最终提供给对白 Prompt 的节点。
4. 增加回归测试覆盖：
   - LLM 返回 `general_recall` 时，明确“在哪里”问句被校正为定位方向；
   - 明确提到千早时，最终结果保留千早相关 `person` / `identity` 节点；
   - 无实时位置注入时，不把记忆推断错误误报成检索系统异常。

## 证据入口

- Unity 结构化快照：`aisc_debug.memory_retrieval_snapshot`
- 后端日志：[backend.log](/F:/GameProject/unity/AISc/backend/logs/backend.log:20884)
- 方向解析：[retrieval_direction.py](/F:/GameProject/unity/AISc/backend/src/memory/retrieval_direction.py:258)
- 最终重排：[retrieval.py](/F:/GameProject/unity/AISc/backend/src/memory/retrieval.py:257)

## 当前状态

已修复：`memory_direction` 现保留一次调用并由本地明确实体/定位语义校准；单次向量 query 不再混入场景或摘要；最终选择使用六分量评分和完整原子条目预算。未注入实时世界位置，缺证据时仍保持既有不确定语义。实施和验证见 `docs/AIChanges/Memory/2026-07-17_LLM检索想法向量路由修复_execution.md`。
