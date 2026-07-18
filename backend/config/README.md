# 后端配置目录

## 文件夹功能

保存后端运行配置、角色配置和可调整参数。

## 文件夹内容

配置应按功能命名并保持稳定主键；跨端共享的地点、行为和物品数据应放在 `shared/`，不要在此重复定义。

`prompt/` 保存后端 LLM task 的系统契约、响应契约和标签渲染配置；业务模块通过 `backend/src/prompting/` 读取。

`initial_knowledge.json` 是冷启动初始事实的唯一配置入口。事实 ID、知识范围、来源类型、权限人物和确定性投影模板必须通过 `backend/src/memory/initial_knowledge.py` 校验；不要在 NPC profile 或 `StateManager` 中重复添加共享事实。

`memory_retrieval.yaml` 是记忆路由策略的唯一配置入口。每个 `player_dialogue`、`npc_dialogue`、`nightly_impression` mode 都必须完整保存三种策略参数块、`query` 字符预算和六分量 `final_scoring`；strategy 只允许 `local_only`、`llm_guided_local`、`llm_full_route`。配置在后端启动时严格校验，未知字段、负数、越过安全上限、类型先验超过 0.05 和跨字段冲突会阻止启动，修改后重启生效。
