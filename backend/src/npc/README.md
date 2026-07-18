# NPC 模块

## 文件夹功能

负责 NPC 日程规划、互动后重规划、记忆/印象推理和社交语义决策。

## 文件夹内容

包含语义引擎、状态推理、计划生成和行为约束。Unity 侧表现与运行时权威状态位于 `Assets/Scripts/NPC/`。

## 核心入口

- `behavior_engine.py`: 日程生成、Unity 权威重规划 facade 与社交语义意愿；不再执行物理 tick 或任务监督。
- `social_session.py`: NPC-NPC 纯内容请求幂等缓存和有效 COMPLETE 后的记忆提交；不持有会合、超时或 reservation。
- `npc_dialogue.py`: READY 后生成对话内容；由 session coordinator 在 COMPLETE 后提交记忆。
- `task_catalog.py`: 共享 action-location-role affordance 查询与校验。
- `daily_schedule.py`: 冻结时间/世界版本下的日程规划与互动后完整替换；`NPC_SCHEDULE_REPLAN_REQUEST` 只读取 Unity 回传的剩余日程和 base revision。

当前默认社交链由 Unity 物理候选扫描、后端语义意愿、Unity session/reservation 和会合后的后端内容响应组成。旧后端 PREPARE/CANCEL 会合监督、物理扫描、`TaskTracker` 节点监督和 `NPC_TASK_STATUS_QUERY` 已删除。

NPC 计划、社交决策、印象刷新和 NPC-NPC 对话的 LLM 调用不设置 `max_tokens` 硬上限；轮数、条目数、字数和 JSON 格式使用 Prompt 软约束。

计划与社交意愿 Prompt 使用 `src/prompting.PromptAssembler`；`_task_catalog.validate_task` 与本地 fallback 仍是最终约束。

日程 planner 的 JSON 输出必须使用已列出的 candidate ID、合法且严格递增的 `HH:MM`，并在候选足够时保持 6-10 条；不满足时整体进入确定性 fallback。Unity 的 pending、in-flight、任务裁决、P0/need 和运行时状态不持久化到 Python。
计划与社交意愿 Prompt 使用 `src/prompting.PromptAssembler`；`_task_catalog.validate_task` 与本地 fallback 仍是最终约束。

`StateManager.cold_start()` 只编排初始知识事实加载、观察者投影和图/向量写入；scope、模板和权限规则统一位于 `src/memory/initial_knowledge.py`，初始投影来源写入 `memory_initial_projections`。

`player_impression_refresh.py` 独立负责午夜固定玩家目标的输入冻结、5 次有界并发生成、fallback、顺序提交和次日社交基准策略。`StateManager.nightly_refresh()` 仅保留兼容委托；NPC-NPC 基准印象和白天 delta 不再由午夜重建或清空。
