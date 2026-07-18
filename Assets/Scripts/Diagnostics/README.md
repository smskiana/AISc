# Diagnostics 脚本目录

## 文件夹功能

保存 Unity 运行时业务诊断聚合、结构化快照和 AI 调试读取接口。

## 核心入口

- `AiscDiagnostics.cs`: 聚合运行状态、健康报告、协议轨迹、NPC 任务、NPC 运行时状态、日程和逐轮对话检索快照。
- `DiagnosticModels.cs`: 诊断结果 DTO；只表达只读状态，不承载业务操作。

Unity MCP 适配器位于 `Assets/Scripts/Editor/Diagnostics/`。运行时诊断模块不得依赖 UnityEditor 或 MCP 包。

`aisc_debug` 的 `conversation_retrieval_snapshot` 可按 `conversation_id` 和 `speaker_id` 查询当前发言、近期对白、图起点、策略、结构化方向、检索想法、单次向量用途、图候选、最终条目评分/淘汰、停止和失败原因。`memory_retrieval_snapshot` 通过后端只读入口按 trace、NPC、mode、strategy 查询通用检索快照。

`aisc_debug.npc_runtime_state_snapshot` 返回 Unity 权威 NPC 运行时状态，包括 emotion、energy、sociability、current_need、is_asleep、lingering_concern，以及最近一次 `NpcStateEffect` 的 operation、应用/拒绝状态和原因。迟到 effect 应表现为 `last_effect_status=rejected` 与稳定拒绝原因。

`aisc_control` 是 `UNITY_EDITOR` 条件编译保护的白名单控制工具，支持 `start_new_game`、`start_dialogue`、`send_player_choice`、`end_dialogue`、`run_midnight_settlement` 和 `run_memory_retrieval_probe`；工具和对应业务入口均不进入 Player 构建。午夜入口复用正式 `SleepController` 流程，完成状态用 `aisc_debug.midnight_snapshot` 等待验证；检索探针不允许 strategy 覆盖，也不恢复 clarity 或写持久记忆。

`aisc_debug` 的 `initial_knowledge_projection_snapshot` 通过后端只读 HTTP 入口查询冷启动事实投影，返回 source fact、权限依据、来源元数据、实际 node/edge/person node ID 和稳定 failure reason。Unity 侧不读取或重建后端 SQLite/LanceDB。

`aisc_debug.player_reply_suggestion_snapshot` 通过后端只读 HTTP 入口按 `reply_trace_id`、`npc_id` 和 `limit` 查询快捷回复安全摘要：期望发言者/接收者、上下文键、选择数量、定长预览、拒绝原因、fallback、失败原因和耗时。Unity 只代理 DTO，不读取完整 Prompt、完整对白、玩家记忆或原始 LLM 输出。

`aisc_debug.runtime_snapshot` 还包含 `world_preparation`：操作 ID、flow、phase、活跃状态、进度下限和失败原因。该 DTO 只反映协议状态，不携带加载 UI 文案或 LLM 原文。

`aisc_debug.midnight_snapshot` 通过后端只读入口返回午夜 operation ID、阶段、`success / partial_failure / failed`、固定方向来源、LLM 方向调用数、每 owner 检索 trace、印象与提取结果、非法节点/边、失败 owner 和各阶段墙钟。
