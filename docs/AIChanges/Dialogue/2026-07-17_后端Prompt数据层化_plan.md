> 执行记录: [2026-07-17_后端Prompt数据层化_execution.md](2026-07-17_后端Prompt数据层化_execution.md)

# 后端 Prompt 数据层化执行案

## 状态

- Status: Planned
- 日期: 2026-07-17
- 主要功能域: 对话系统
- 关联功能域: NPC 行为、记忆系统、测试与诊断
- 方案来源: 用户要求精简后端 prompt，将必要系统提示词以外的角色、地点、语气、氛围和行为倾向离散化、标签化，并从业务逻辑中摘除到专门数据层。

## 一、需求理解

当前后端 prompt 混在 `dialogue`、`npc`、`memory` 的业务逻辑内，包含三类不同性质的内容：

1. 系统契约：任务目标、输出格式、硬性边界、不可虚构规则。
2. 动态事实：当前时间、地点、动作、关系印象、记忆检索结果、候选任务。
3. 内容风格：角色性格、说话习惯、地点氛围、可聊话题、社交倾向。

本轮目标不是重写对话、行为和记忆算法，而是先建立统一 prompt 数据层和组装层，让业务逻辑只提交结构化上下文，由 prompt module 负责读取标签、选择任务规格和渲染 messages。

## 二、现行口径约束

1. Dialogue Workstream:
   - 玩家正式对话、NPC-NPC 闲聊、快捷回复都必须继续注入现场感知。
   - 玩家昵称继续通过 `player_name.py` 渲染，不在 prompt 中硬编码旧默认昵称。
   - 首遇 prompt 不诱导“好久不见 / 你一点都没变”。
   - 事实守门继续只拦未发生玩家行动的亲历式断言。
   - 后端 LLM 调用不设置 `max_tokens` 硬上限，长度和格式仍由 prompt 软约束、解析和业务校验收口。
2. NpcBehavior Workstream:
   - 日计划和行为重排必须只使用固定 `action_id` 与 `location_id`。
   - LLM 只在允许候选中做选择或补理由，不得自由生成 Unity 不认识的地点或行为。
3. Memory Workstream:
   - 记忆图和向量层口径不改。
   - 玩家正式对话检索仍按现有结构化输入刷新，不把话题实体偷加成图起点。
   - 记忆相关 LLM 输出继续由 prompt 软约束和解析校验共同收口。
4. 本计划不涉及 Unity 场景、Prefab、SerializeField 或 UI 资产层修改，因此不触发 Unity MCP 资产编辑流程。

## 三、目标边界

### 3.1 本轮实施目标

1. 新增后端 prompt 数据层目录，集中保存任务规格、系统契约、响应契约和可复用标签格式规则。
2. 新增 `backend/src/prompting/` module，提供窄 interface：

   ```python
   messages = prompt_assembler.build(task_id, context)
   ```

3. 将以下 prompt 从业务逻辑中迁出：
   - 玩家正式对话 prompt。
   - NPC-NPC 对话 prompt。
   - 玩家快捷回复建议 prompt。
   - NPC 日计划 prompt。
   - NPC 社交意愿 prompt。
   - 夜间熟人印象 prompt。
   - 记忆提取、记忆融合、多跳路由 prompt。
4. 将角色、地点和行为相关的大段风格描述优先压缩为标签或短字段，业务逻辑只传 ID、状态和上下文。
5. 保持既有功能行为基本不变，先完成结构迁移和快照测试，再做真实 LLM 质量调优。

### 3.2 明确不做

1. 不改变记忆图起点策略、路由算法和向量兜底策略。
2. 不改变 NPC 行为调度、任务执行闭环、社交会合协议。
3. 不改 Unity 前端协议和资产。
4. 不把 prompt 白名单变成事实系统。
5. 不把角色标签扩成新的复杂人格本体；第一版只做轻量标签化。

## 四、目标架构

### 4.1 数据层

新增目录：

```text
backend/config/prompt/
  README.md
  system_contracts.yaml
  task_specs.yaml
  response_contracts.yaml
  tag_rendering.yaml
```

职责：

1. `system_contracts.yaml`
   - 保存各任务必要系统提示。
   - 只包含任务目标、硬规则、事实边界和输出纪律。
2. `task_specs.yaml`
   - 定义 `task_id`、输入上下文字段、使用的 system contract、响应契约、温度建议和标签渲染策略。
3. `response_contracts.yaml`
   - 集中保存各任务响应形态：对白类为自然文本或既有多行对白格式；计划、快捷回复、印象、记忆提取和路由等结构化任务才声明最短字段契约、数量要求和解析要求。
   - prompt 正文不放冗长 JSON 示例；结构化任务只渲染紧凑字段清单，例如字段名、类型、数量和“仅返回可解析对象”，避免把 token 浪费在格式样板上。
4. `tag_rendering.yaml`
   - 定义角色标签、地点标签、关系标签、记忆标签如何转成简短 prompt 段落。
   - 第一版只做纯文本渲染，不引入模板语言。

已有 profile 扩展方向：

```json
{
  "persona_tags": ["直率", "乐观", "行动派"],
  "speech_tags": ["语速快", "直呼名字", "想到什么说什么"],
  "social_tags": ["主动", "热情", "容易靠近"]
}
```

地点 profile 扩展方向：

```json
{
  "mood_tags": ["干净", "整洁", "温馨", "安静"],
  "sensory_tags": ["花香", "自然光", "湿润泥土"],
  "topic_tags": ["今天最好看的花", "给谁选花"]
}
```

兼容策略：

1. 第一阶段保留 `personality`、`speech_style`、`atmosphere` 等旧字段。
2. 新渲染器优先读新标签字段；缺失时从旧字段生成兼容短行。
3. 旧字段不在本轮删除，避免影响存档、测试和未迁移调用。

### 4.2 代码层

新增 module：

```text
backend/src/prompting/
  README.md
  __init__.py
  prompt_context.py
  prompt_registry.py
  tag_formatter.py
  prompt_assembler.py
```

职责划分：

1. `prompt_context.py`
   - 定义 `PromptContext` 或按任务拆分的轻量 dataclass。
   - 只承载结构化事实，不包含长 prompt 文案。
2. `prompt_registry.py`
   - 读取 `backend/config/prompt/*.yaml`。
   - 对外提供 `get_task_spec(task_id)`、`get_contract(contract_id)`。
3. `tag_formatter.py`
   - 把 NPC profile、location profile、impression、memory、task candidates 压成短标签块。
   - 统一处理空值、截断和旧字段兼容。
4. `prompt_assembler.py`
   - 唯一负责生成 `messages: list[dict]`。
   - 对业务调用者暴露 `build(task_id, context)`。
   - 只按任务契约渲染提示，不统一强迫 LLM 输出 JSON；对白类任务不得额外包一层 JSON 或要求模型返回多余结构。
   - 对必须机器解析的任务，也只渲染最短结构化约束，不输出完整 JSON 样例、Markdown 代码块或重复字段说明。

业务模块迁移后只保留：

```python
messages = self.prompt_assembler.build("player_dialogue", context)
```

## 五、任务规格设计

第一版固定以下 `task_id`：

| task_id | 原调用点 | 输出 | 备注 |
|---|---|---|---|
| `player_dialogue` | `PromptBuilder.build` | 对话文本流 | 继续只返回 system message，由现有对话链追加用户发言 |
| `npc_dialogue` | `PromptBuilder.build_npc_to_npc` | 多行对白 | 保持既有整段生成方式 |
| `player_reply_suggestions` | `PromptBuilder.build_player_reply_suggestions` | `{"choices":[]}` | 保持恰好 3 条 |
| `npc_daily_plan` | `BehaviorEngine._generate_plan_for_npc` | JSON 数组 | 只允许候选任务 |
| `npc_replan_after_social` | `BehaviorEngine._replan_after_social` | JSON 数组 | 只生成 2-3 条后续 |
| `npc_social_intent` | `BehaviorEngine._wants_to_talk` | `{"want_to_talk": bool}` | 保持本地 fallback |
| `nightly_impression` | `StateManager._run_impression_task` | impression JSON | 保持字段兼容 |
| `memory_extract` | `MemoryManager.extract_from_events` | nodes/edges JSON | 保持 schema |
| `memory_merge` | `EvolutionEngine._merging` | 1 句概括文本 | 保持第一版硬阈值行为 |
| `memory_route` | `RetrievalEngine._select_edges_with_llm` | `{"selected":[]}` | 不改变路由起点 |

## 六、迁移步骤

### 阶段 1：建立 prompt 数据层和读取 module

涉及文件：

```text
backend/config/prompt/README.md
backend/config/prompt/system_contracts.yaml
backend/config/prompt/task_specs.yaml
backend/config/prompt/response_contracts.yaml
backend/config/prompt/tag_rendering.yaml
backend/src/prompting/README.md
backend/src/prompting/__init__.py
backend/src/prompting/prompt_context.py
backend/src/prompting/prompt_registry.py
backend/src/prompting/tag_formatter.py
backend/src/prompting/prompt_assembler.py
```

验收：

1. 单元测试能加载所有 task spec。
2. 所有 task spec 引用的 contract、schema、tag rendering key 都存在。
3. 缺失可选标签时不抛异常，使用旧字段兼容。

### 阶段 2：迁移 Dialogue prompt

涉及文件：

```text
backend/src/dialogue/prompt_builder.py
backend/src/application/runtime.py
backend/tests/
```

步骤：

1. 在 `PromptBuilder` 构造时注入或创建 `PromptAssembler`。
2. `build()` 改成构造 player dialogue context，再调用 assembler。
3. `build_npc_to_npc()` 改成构造 NPC-NPC context。
4. `build_player_reply_suggestions()` 改成使用 `player_reply_suggestions` task。
5. 保留 `_load_profile`、状态、感知、记忆检索等数据收集逻辑。
6. 删除或停止使用模块顶部大段 prompt 常量。

验收：

1. 快照测试覆盖三类 messages。
2. 玩家昵称 token 仍由 `render_player_tokens` 处理。
3. 首遇规则、事实边界、现场感知和关系印象仍出现在渲染结果中。

### 阶段 3：迁移 NPC 行为 prompt

涉及文件：

```text
backend/src/npc/behavior_engine.py
backend/tests/
```

步骤：

1. 日计划、社交后重排、社交意愿改走 `PromptAssembler`。
2. `BehaviorEngine` 继续负责构造 task candidates、routine、plan context 和 fallback。
3. prompt contract 明确 “只能使用候选 action/location”。
4. 保留现有 `_task_catalog.validate_task` 作为硬校验。

验收：

1. LLM 输出非法 action/location 时仍会被过滤。
2. 无 LLM 时仍走既有 fallback plan。
3. 社交意愿 JSON 解析失败时仍回退本地规则。

### 阶段 4：迁移 StateManager 印象 prompt

涉及文件：

```text
backend/src/npc/state_manager.py
backend/tests/
```

步骤：

1. `_run_impression_task()` 改走 `nightly_impression` task。
2. 保持输出字段：`baseline_impression`、`speech_hint`、`approach_bias`、`emotion_baseline`、`lingering_concern`。
3. 保留 `_fallback_impression()`。

验收：

1. 字段缺失时仍填默认值。
2. `approach_bias` 仍 clamp 到 `[-1.0, 1.0]`。
3. 夜间批量刷新测试不回退。

### 阶段 5：迁移 Memory prompt

涉及文件：

```text
backend/src/memory/manager.py
backend/src/memory/evolution.py
backend/src/memory/retrieval.py
backend/tests/
```

步骤：

1. 记忆提取 prompt 改走 `memory_extract` task。
2. 记忆融合 prompt 改走 `memory_merge` task。
3. 多跳路由 prompt 改走 `memory_route` task。
4. 不修改图结构、不修改路由起点、不修改本地排序 fallback。

验收：

1. 提取 JSON schema 与旧解析器兼容。
2. 路由 LLM 失败仍回退本地排序。
3. 记忆融合仍生成单句结果，并保留旧边继承和归档逻辑。

### 阶段 6：标签化 profile 数据

涉及文件：

```text
backend/config/npc_profiles/*.json
backend/config/location_profiles/*.json
```

步骤：

1. 给 5 个 NPC profile 增加 `persona_tags`、`speech_tags`、`social_tags`。
2. 给地点 profile 增加 `mood_tags`、`sensory_tags`、`topic_tags`。
3. 第一版只新增字段，不删除旧字段。
4. `tag_formatter` 优先读取新字段；缺失则降级旧字段。

验收：

1. 所有 NPC 都能渲染角色标签块。
2. 所有主要地点都能渲染地点标签块。
3. 未补标签的地点或 spot 不影响运行。

## 七、测试计划

新增或调整测试：

```text
backend/tests/test_prompt_registry.py
backend/tests/test_prompt_assembler.py
backend/tests/test_dialogue_prompt_messages.py
backend/tests/test_behavior_prompt_messages.py
backend/tests/test_memory_prompt_messages.py
```

测试重点：

1. task spec 完整性。
2. 标签缺失兼容。
3. 结构化任务存在最短响应契约；对白类任务确认不被额外 JSON 化。
4. 玩家昵称 token 渲染。
5. 不出现旧默认昵称硬编码。
6. 不出现自由地点 / 自由行为诱导。
7. 玩家对话动态上下文仍包含当前发言、滚动摘要、参与者关系和检索结果。
8. 渲染后的 prompt 不包含冗长 JSON 样例、Markdown JSON 代码块或重复格式模板。

建议运行：

```text
pytest backend/tests
```

如全量测试时间过长，先跑新增 prompt 测试和既有 dialogue / npc / memory 相关测试，再补全量。

## 八、诊断与控制钩子

本轮主要改变 prompt 组装结构，不改变业务阶段语义；但按项目诊断规则，需要检查并补齐可观测性。

第一版建议：

1. 在后端日志中记录 `task_id`、contract id、schema id、context 摘要长度，不记录完整私密内容。
2. 若现有 `aisc_debug` 已能查看玩家对话检索快照，本轮不改变其业务 DTO。
3. 如新增 prompt 诊断 DTO，建议提供：
   - `task_id`
   - `context_keys`
   - `system_contract_id`
   - `schema_id`
   - `rendered_sections`
   - `message_count`
4. 不新增 `aisc_control` 行为，因为本轮不需要编辑器控制新动作。

验收：

1. execution 中必须说明诊断钩子是否新增。
2. 若未新增，必须说明原因：本轮为 prompt 渲染结构迁移，业务状态和阶段 DTO 不变。

## 九、文档回写

实施完成后需要检查并视实际修改回写：

```text
backend/src/dialogue/README.md
backend/src/npc/README.md
backend/src/memory/README.md
backend/config/README.md
docs/Workstreams/Dialogue/README.md
docs/Workstreams/NpcBehavior/README.md
docs/Workstreams/Memory/README.md
```

若新增 `backend/src/prompting/`，必须写 `README.md`，说明：

1. module 负责 prompt 数据读取和 messages 组装。
2. 业务逻辑不得新增大段 prompt 常量。
3. 新 LLM task 应先注册 `task_id` 与响应契约；只有确实需要机器解析的任务才使用结构化契约，且 prompt 正文只能出现最短字段约束。
4. 标签数据优先放 profile/config，不放业务逻辑。

## 十、风险与处理

1. 风险：一次性迁移所有 prompt 容易造成对话质量漂移。
   - 处理：先做结构迁移和快照测试，真实 LLM 调优单独小步进行。
2. 风险：标签过短导致角色味道变淡。
   - 处理：保留旧字段兼容，第一版标签渲染允许短标签 + 少量口癖。
3. 风险：YAML 配置错误导致运行期失败。
   - 处理：启动或测试阶段校验全部 task spec 引用完整性。
4. 风险：Memory prompt schema 被压缩后解析失败。
   - 处理：memory 迁移最后做，保持旧输出示例完整，不在同轮改解析器。
5. 风险：`PromptBuilder` 继续变重。
   - 处理：只让它收集 dialogue 上下文；prompt 渲染职责迁到 `PromptAssembler`。

## 十一、验收标准

1. 代码中不再新增大段业务 prompt 常量；已迁移任务的 prompt 文案来自 `backend/config/prompt/`。
2. `PromptAssembler.build(task_id, context)` 能覆盖第一版 10 个任务。
3. 角色、地点、社交倾向和语气主要由标签字段渲染。
4. 旧 profile 字段仍兼容，未迁移数据不导致运行失败。
5. 既有 dialogue、npc、memory 关键测试通过。
6. 玩家正式对话仍每轮使用最新发言和近期对白触发既有图检索。
7. NPC 行为计划仍不能输出未注册 action/location。
8. 记忆提取、融合和路由的输出 schema 与解析器兼容。
9. 渲染后的 prompt 不包含冗长 JSON 示例；结构化任务只保留必要字段约束。
10. 相关 README / Workstream 与实际架构一致。
11. execution 明确记录诊断钩子处理、测试结果、未完成项和真实 LLM 调优是否暂缓。

## 十二、执行会话要求

本计划预计新增文件超过 2 个、修改文件超过 3 个，属于复杂实现。按项目规则，实际代码实现应在新的执行对话中进行，并以本文件作为唯一方案来源。

如果执行中发现方案无法落地、边界扩大到算法重写、或需要改变 Dialogue / NpcBehavior / Memory 的系统口径，应停止实现，回到方案阶段更新本文件，不得在执行对话中另建第二份 plan。
