> 设计方案: [2026-07-17_冷启动初始知识投影_plan.md](2026-07-17_冷启动初始知识投影_plan.md)

# 冷启动初始知识投影执行记录

## 实际改动

1. 新增 `backend/config/initial_knowledge.json`，将原四条共享背景迁入唯一事实源，并补充主要人物公开身份、共同经历和樱的私密事实。
2. 新增 `backend/src/memory/initial_knowledge.py`，实现稳定 ID、五种知识范围、事实级排除、模板白名单、确定性 projection ID 和观察者视角 DTO。
3. 新增 `backend/src/memory/initial_knowledge_diagnostics.py`，从事实配置、SQLite 来源表、向量层和实际图边组合只读诊断快照。
4. `StateManager.cold_start()` 改为加载一次事实配置并按观察者投影；投影节点 ID、人物边 ID 均稳定，个人 `core_memories` 保持原路径。
5. SQLite 新增 `memory_initial_projections` 表、索引和 CRUD；checkpoint 的记忆表清单已同步，冷启动会清空来源表。
6. 新增后端 `GET /api/npc/{npc_id}/initial_knowledge_projection_snapshot`，支持 `source_fact_id` 和 `include_excluded`。
7. Unity 新增初始知识诊断 DTO、`AiscDiagnostics.GetInitialKnowledgeProjectionSnapshot` 和 `aisc_debug` action；Unity 只通过后端只读 HTTP 查询，不重建数据库状态。
8. 同步配置、Memory/NPC/API、Unity Diagnostics README 与 Memory Workstream 入口。

## 验证

- `python -m pytest backend/tests/test_initial_knowledge.py -q`：5 passed，3 subtests passed。
- `python -m pytest backend/tests/test_initial_knowledge_cold_start.py -q`：3 passed。
- `python -m pytest backend/tests/test_memory_checkpoint.py -q`：6 passed。
- `python -m pytest backend/tests -q`：68 passed，3 subtests passed。
- 冷启动规模 smoke：每个 NPC 11/10/10/10/10 条投影；总计 51 条投影、100 个 SQLite 节点、134 条边、100 条向量写入；投影节点最大实际连接边数为 2；临时 SQLite + 模拟向量层耗时 2.333 秒。

## 诊断验收

- included 项返回事实 ID、projection/node ID、权限依据、来源类型、confidence、importance、人物/地点 ID、实际 edge ID 和 person node ID。
- excluded 项只返回排除规则和原因，`node_id`、`projection_id`、`edge_ids`、`person_node_ids` 均为空。
- 私密事实只进入主体图；公开身份事实在观察者图中有事实节点和 `involved` 人物边。
- 重复冷启动保持同一 observer + fact 的来源、节点和边 ID，不累积重复记录。

## 未完成项与范围说明

- 当前环境未安装 Unity Editor 可执行文件，无法运行 Unity EditMode 测试和 Play Mode 对话验收；Unity DTO/非 PlayMode 稳定失败测试已补齐，但实际后端 HTTP 联调仍待在可启动 Unity 环境验证。
- 本轮未修改 Unity 场景、Prefab、SerializeField、UI 或其他资产层内容，因此未触发 Unity MCP 资产编辑流程。
- 未提供旧存档重建工具；新知识只在 `cold_start()` 新图初始化时生效，旧存档不会静默注入。
- 未改变对话检索算法、图搜索深度、候选排序、Prompt 或 ADR-0001 的独立轻量图边界。
