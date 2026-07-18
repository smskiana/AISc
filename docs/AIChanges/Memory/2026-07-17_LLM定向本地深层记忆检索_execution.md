> 设计方案: [2026-07-17_LLM定向本地深层记忆检索_plan.md](2026-07-17_LLM定向本地深层记忆检索_plan.md)

# 三策略可配置记忆路由与本地深层检索 - 执行记录

## 1. 执行结论

已按 plan 完成后端检索减重、三策略接入、方向解析、本地深搜、完全 LLM 路由、诊断 trace、编辑器控制探针和入口文档同步。没有修改场景、Prefab、UI、SerializeField 连线、正式业务协议 schema 或数据库 schema。

当前实现完成的是工程 seam 和离线验证；真实 LLM / 正式隔离图样本长测与 Unity Play Mode 真实对话仍是未完成验收项，不能将其伪装成已验证结果。

## 2. 实际改动

### 后端检索与配置

- 新增 `retrieval_contracts.py`：集中受控枚举、请求 / 结果、方向、policy、深搜结果和 `RetrievalTrace` DTO。
- 新增 `retrieval_policy.py` 与 `backend/config/memory_retrieval.yaml`：启动时严格读取三业务 mode；默认玩家=`llm_guided_local`、NPC-NPC=`local_only`、夜间=`llm_guided_local`。
- 新增 `retrieval_direction.py`：本地方向、一次 `memory_direction` LLM、JSON 白名单清洗、mention 稳定 ID 解析、数据字符预算和显式降级原因。
- 新增 `deep_retrieval.py`：固定 `self + 当前对话对象` 起点、批量邻接、beam / 深度 / 展开边预算、archived / allowed 过滤、路径评分、停止和失败语义。
- 新增 `llm_graph_retrieval.py`：竞争候选逐跳 `memory_route`，不使用本地置信阈值跳过；调用失败才显式 `degraded_to_local`，调用预算耗尽返回 `budget_exhausted`。
- 新增 `retrieval_diagnostics.py`：固定容量安全 trace provider。
- `retrieval.py` 收敛为 facade，保留旧字符串入口和历史测试私有 seam 的薄委托；最终节点重排、clarity 恢复和旧日志兼容仍统一在 facade。
- `sqlite_client.py` 新增 `get_directional_neighbors_batch` 领域化批量 adapter，检索模块不访问原始 SQL。
- `main.py` 新增只读 `GET /api/memory/retrieval_snapshot` 和编辑器探针 `POST /api/memory/retrieval_probe`。

### Prompt、诊断与控制

- 新增 `memory_direction` task、system contract 和 response contract；不设置 `max_tokens`。
- 对话诊断 DTO 增加 trace、策略、方向、mention、锚点、层统计、路径、向量用途、停止和降级字段。
- Unity `DiagnosticModels.cs` 增加通用记忆快照和只读 probe 结果；`WebSocketClient` 增加通用 trace 缓存。
- `aisc_debug` 增加 `memory_retrieval_snapshot`；`aisc_control` 使用 handler 注册表增加 `start_dialogue`、`send_player_choice`、`end_dialogue`、`run_memory_retrieval_probe`，均受 `UNITY_EDITOR` 保护。
- 已按 `UnityMCPUsageRules.md` 通过 Unity MCP 刷新脚本、读取编辑器状态和检查 Console；本轮没有资产层变更。

### 测试与工具

- 新增 policy、direction、deep retrieval 测试。
- 新增 `backend/scripts/evaluate_deep_retrieval.py`，在固定图 / fake LLM 上快速跑三 mode × 三 strategy 九组合。
- 更新 Memory / Dialogue / Diagnostics / backend 配置、测试和脚本 README 及 Workstream 入口。

## 3. 最终默认参数

参数以 `backend/config/memory_retrieval.yaml` 为准。保留 plan 指定值：

| mode | 默认 strategy | 本地 max_depth / beam_width | 方向上下文字符上限 | 向量 Top-K / 最终节点 |
|---|---|---:|---:|---:|
| `player_dialogue` | `llm_guided_local` | 4 / 8 | 3000 | 8 / 5 |
| `npc_dialogue` | `local_only` | 2 / 4 | 2000 | 4 / 3 |
| `nightly_impression` | `llm_guided_local` | 6 / 12 | 6000 | 12 / 6 |

完全 LLM 路由分别使用各 mode 的 `max_hops`、frontier、候选字符和 `max_llm_route_calls`，不复用本地 beam 字段。

## 4. 验证结果

- `python -m pytest backend/tests -q`：`74 passed, 3 subtests passed`。
- `python backend/scripts/evaluate_deep_retrieval.py`：九组合均完成；`local_only` 0 次 LLM，`llm_guided_local` 正常 fake 场景 1 次方向 LLM，`llm_full_route` 仅在存在竞争候选的跳次调用 route LLM；本轮离线样本未连接真实 API。
- Unity MCP EditMode：`10/10 passed`。
- Unity MCP PlayMode：测试运行成功但当前没有 PlayMode 测试，结果为 `0 passed / 0 failed`，不等同于真实对话验收。
- Unity Console：未发现本轮新增 C# 编译错误；保留项目原有 `GameManager._serverUrl` 未使用警告。期间 MCP transport 还出现过一次 `WebSocket is not initialised` warning，未形成项目脚本编译错误。
- FastAPI 入口导入检查通过，新增两个 retrieval endpoint 已注册。

## 5. 未完成项与后续验收

1. 在隔离 SQLite / LanceDB 副本上跑真实图样本，比较九组合方向正确率、召回、P50 / P95、字符量和 LLM 次数。
2. Unity 后端启动后用 `aisc_control.start_new_game`、`start_dialogue`、`send_player_choice`、`end_dialogue` 完成真实 Play 流程，并用 `aisc_debug` 读取最后一轮 trace。
3. 真实 Play 场景验证“千早在哪”“为什么觉得龙之介有才能”和无知识问题。
4. 当前没有新增游戏内策略设置、运行时策略覆盖协议或存档字段；如需这些能力必须另开方案。

