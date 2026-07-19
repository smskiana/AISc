# Diagnostics 脚本目录

## 文件夹功能

保存 Unity 运行时业务诊断聚合、结构化快照和 AI 调试读取接口。

## 核心入口

- `AiscDiagnostics.cs`: 聚合运行状态、健康报告、协议轨迹、NPC 任务、NPC 运行时状态、日程和逐轮对话检索快照。
- `DiagnosticModels.cs`: 诊断结果 DTO；只表达只读状态，不承载业务操作。

Unity MCP 适配器位于 `Assets/Scripts/Editor/Diagnostics/`。运行时诊断模块不得依赖 UnityEditor 或 MCP 包。

## 工具选择

- 需要确认 Unity 运行时关键状态、阶段、失败原因、revision 或关联 ID 时，先用只读 `aisc_debug`。
- 需要稳定触发正式业务 seam 时，使用 `aisc_control` 的白名单 action，再用 `aisc_debug` 读取结果；不得把控制 action 的成功响应当作业务完成证据。
- Console 用于编译错误、异常栈和未被结构化 DTO 覆盖的编辑器问题；已有结构化快照时不能只凭零散日志判断。
- 自动化逻辑回归见 `Assets/Tests/README.md`。测试方案先从 `docs/Workstreams/TestingAndDiagnostics/README.md` 选择工具，不需要预读本文所有 action 细节。

`aisc_debug` 的 `conversation_retrieval_snapshot` 可按 `conversation_id` 和 `speaker_id` 查询当前发言、近期对白、图起点、策略、结构化方向、检索想法、单次向量用途、图候选、最终条目评分/淘汰、停止和失败原因。`memory_retrieval_snapshot` 通过后端只读入口按 trace、NPC、mode、strategy 查询通用检索快照。

`aisc_debug.npc_runtime_state_snapshot` 返回 Unity 权威 NPC 运行时状态，包括 emotion、energy、sociability、current_need、is_asleep、lingering_concern，以及最近一次 `NpcStateEffect` 的 operation、应用/拒绝状态和原因。迟到 effect 应表现为 `last_effect_status=rejected` 与稳定拒绝原因。

`aisc_debug.day_plan_snapshot` 返回活动 segment、活动任务、work/rest 剩余计数、边界、mutation 和最近终态；`daily_schedule_snapshot` 仅作为兼容视图。后端 trace 只包含候选分组计数、证据 ID、校验/fallback 阶段、耗时与稳定失败原因，不暴露 Prompt、模型原文或 embedding。
空 replan operation 不关联同 NPC 的其他 trace；fallback reason 最多返回 50 条，避免候选规模放大诊断载荷。
planner 拒绝时 `failure_detail` 只返回最多 200 字符的异常消息，用于区分 JSON、候选、时间和字段契约错误；不包含 Prompt 或模型原文。

`aisc_control` 是 `UNITY_EDITOR` 条件编译保护的白名单控制工具，支持既有对话、午夜、检索入口、`run_daily_schedule_probe` 和 `run_npc_social_probe`。日程探针覆盖固定双队列、provider timeout、17:00、社交锁、失败推进和迟到 revision；社交探针覆盖 complete/player_preempt/rendezvous_failure/late_content_revision。探针复用正式 planner/runtime seam，写入范围固定为 `isolated_in_memory_only`，不修改场景、存档、后端或业务计划库。工具和对应业务入口均不进入 Player 构建。

真实 PlayMode 社交长链使用 `start_npc_social_playmode_probe`，只允许 `cross_location_complete / player_preempt / rendezvous_failure`，固定参与者为 `sakura/chihaya`，固定起点为 `street.arcade/street.vending_machine`，会合点为 `street.crossroad`。它调用正式协议控制器、真实 NPC 移动和后端内容链；玩家抢占调用正式玩家对话入口，会合失败通过第二个真实移动命令取消其中一方的会合移动。写入范围为 `current_play_session_only`，仅用于可丢弃测试数据。

`aisc_debug` 的 `initial_knowledge_projection_snapshot` 通过后端只读 HTTP 入口查询冷启动事实投影，返回 source fact、权限依据、来源元数据、实际 node/edge/person node ID 和稳定 failure reason。Unity 侧不读取或重建后端 SQLite/LanceDB。

`aisc_debug.player_reply_suggestion_snapshot` 通过后端只读 HTTP 入口按 `reply_trace_id`、`npc_id` 和 `limit` 查询快捷回复安全摘要：期望发言者/接收者、上下文键、选择数量、定长预览、拒绝原因、fallback、失败原因和耗时。Unity 只代理 DTO，不读取完整 Prompt、完整对白、玩家记忆或原始 LLM 输出。

`aisc_debug.runtime_snapshot` 还包含 `world_preparation`：操作 ID、flow、phase、活跃状态、进度下限和失败原因。该 DTO 只反映协议状态，不携带加载 UI 文案或 LLM 原文。

`aisc_debug.midnight_snapshot` 通过后端只读入口返回午夜 operation ID、阶段、`success / partial_failure / failed`、固定方向来源、LLM 方向调用数、每 owner 检索 trace、印象与提取结果、非法节点/边、失败 owner 和各阶段墙钟。
