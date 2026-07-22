# Memory 模块

## 文件夹功能

负责 NPC 记忆存储、检索、图关系和夜间维护。

## 文件夹内容

包含图记忆、向量数据层、清晰度、融合、遗忘、印象和上下文检索。当前架构见 Memory Workstream 与 ADR-0001。

`retrieval.py` 是稳定 facade，同时支持结构化 `RetrievalRequest / RetrievalResult` 和旧位置参数兼容入口；策略配置由 `retrieval_policy.py` 读取 `backend/config/memory_retrieval.yaml`。`retrieval_query.py` 负责校验检索想法、至多一条相关近期对白和单次 embedding query；`retrieval_context.py` 负责六分量评分、完整原子条目和字符预算。方向解析、`deep_retrieval.py` 本地深搜和 `llm_graph_retrieval.py` 完全 LLM 路由分别独立测试。当前发言只作为路由与向量 query 的语义依据，不转换成额外图起点。

记忆提取、融合和完全图路由的通用 LLM 调用不设置 `max_tokens` 硬上限；输出规模和 JSON 格式由 Prompt 软约束，并由既有解析与校验收口。方向专项模型由自身冻结的确定性 generation 上限约束。
记忆提取、融合、通用方向解析和多跳路由分别使用 `memory_extract`、`memory_merge`、`memory_direction`、`memory_route` task；不改变图起点、候选排序、向量兜底或解析 fallback。公开路由策略仍为 `local_only`、`llm_guided_local`、`llm_full_route`。配置 version 2 的玩家、NPC 与午夜默认均为 `local_only + [local]`，由确定性本地方向和单次 embedding query 完成实时检索；`general_llm` 保留为显式兼容 provider，R3 v2 / LongCat 实现与测试能力保留但不在生产 provider 注册表中，配置修改需重启后端。

`route_specialist_contract.py` 是 R3 v2 schema、Prompt 和严格输出校验的生产权威；`route_specialist_worker.py` 隔离重模型依赖和 Windows JSONL 子进程；`route_specialist_provider.py` 负责 builder registry、冻结 chain 与生命周期。`RetrievalEngine` 不再构造具体 provider，`GameRuntime` 持有唯一 provider runtime，并在存档恢复后复用。`midnight_coordinator.py` 继续负责午夜阶段、并发边界和诊断聚合；午夜印象通过请求内受控方向 `nightly_fixed_player` 跳过方向模型。

`memory_retrieval_snapshot` 诊断只返回固定容量的 trace 安全摘要，覆盖原问题、provider 请求/采用/回退、冻结模型身份、调用计数、检索想法、单次向量命中、图候选、最终条目评分和淘汰原因；不暴露 Prompt、模型原始输出、完整记忆或机器路径。编辑器 `run_memory_retrieval_probe` 复用正式 facade，禁用 clarity 恢复和持久检索日志。

`midnight_snapshot` 返回 operation ID、阶段、终态、固定方向来源、检索 trace、印象与提取计数、非法输出、局部失败和各阶段墙钟；`partial_failure` 会同步进入跨日完成协议，不会伪装成无错误成功。

冷启动初始知识由 `backend/config/initial_knowledge.json` 提供稳定事实源，`initial_knowledge.py` 负责 scope 权限和观察者视角模板，`initial_knowledge_diagnostics.py` 负责只读来源/图边快照。每个 NPC 仍只写入自己的 SQLite 图和 LanceDB 表，不建立共享运行时记忆图。
