# Memory 模块

## 文件夹功能

负责 NPC 记忆存储、检索、图关系和夜间维护。

## 文件夹内容

包含图记忆、向量数据层、清晰度、融合、遗忘、印象和上下文检索。当前架构见 Memory Workstream 与 ADR-0001。

`retrieval.py` 是稳定 facade，同时支持结构化 `RetrievalRequest / RetrievalResult` 和旧位置参数兼容入口；策略配置由 `retrieval_policy.py` 读取 `backend/config/memory_retrieval.yaml`。`retrieval_query.py` 负责校验检索想法、至多一条相关近期对白和单次 embedding query；`retrieval_context.py` 负责六分量评分、完整原子条目和字符预算。方向解析、`deep_retrieval.py` 本地深搜和 `llm_graph_retrieval.py` 完全 LLM 路由分别独立测试。当前发言只作为路由与向量 query 的语义依据，不转换成额外图起点。

记忆提取、融合和图路由的 LLM 调用不设置 `max_tokens` 硬上限；输出规模和 JSON 格式由 Prompt 软约束，并由既有解析与校验收口。
记忆提取、融合、方向解析和多跳路由分别使用 `memory_extract`、`memory_merge`、`memory_direction`、`memory_route` task；不改变图起点、候选排序、向量兜底或解析 fallback。公开路由策略为 `local_only`、`llm_guided_local`、`llm_full_route`，配置修改需重启后端。`midnight_coordinator.py` 负责午夜阶段、并发边界和诊断聚合；午夜印象通过请求内受控方向 `nightly_fixed_player` 跳过 LLM 方向解析。

`memory_retrieval_snapshot` 诊断只返回固定容量的 trace 安全摘要，覆盖原问题、检索想法、单次向量命中、图候选、最终条目评分和淘汰原因；编辑器 `run_memory_retrieval_probe` 复用正式 facade，禁用 clarity 恢复和持久检索日志。

`midnight_snapshot` 返回 operation ID、阶段、终态、固定方向来源、检索 trace、印象与提取计数、非法输出、局部失败和各阶段墙钟；`partial_failure` 会同步进入跨日完成协议，不会伪装成无错误成功。

冷启动初始知识由 `backend/config/initial_knowledge.json` 提供稳定事实源，`initial_knowledge.py` 负责 scope 权限和观察者视角模板，`initial_knowledge_diagnostics.py` 负责只读来源/图边快照。每个 NPC 仍只写入自己的 SQLite 图和 LanceDB 表，不建立共享运行时记忆图。
