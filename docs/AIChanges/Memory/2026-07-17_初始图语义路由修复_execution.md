> 设计方案: [2026-07-17_初始图语义路由修复_plan.md](2026-07-17_初始图语义路由修复_plan.md)

# 初始图语义路由修复执行记录

## 实施范围

本次按既有 plan 执行，没有创建第二份方案。实现只修改 Python 后端记忆初始化、图检索候选排序、后端测试和 Memory Workstream 状态入口；未修改 Unity 场景、Prefab、SerializeField、UI 结构或资产连线。

## 实际改动

1. `backend/src/memory/edge_semantics.py`
   - 新增 `initial_relationship_clarity()`，将冷启动核心人物的基础认知 clarity 与 bond 解耦。
   - `recognition_importance` 表达“值得稳定记住”，`bond` 只在小范围内微调 clarity。
   - 保留 `resolve_edge_clarity()` 的通用 relationship 规则，未把核心人物冷启动规则塞进通用分支。
2. `backend/src/npc/state_manager.py`
   - `_init_graph()` 创建 self -> person relationship 边时改用 `initial_relationship_clarity(recognition_importance=0.9, bond=bond_val, is_core_person=True)`。
   - 保留 `npc_bonds`、`npc_impressions` 与 `confide_level` 的 bond 语义。
   - 更新原“初始 clarity = bond”注释为“bond 只微调核心人物基础认知 clarity”。
3. `backend/src/memory/retrieval.py`
   - 增加轻量人物 / 地点实体别名匹配，仅在 `RetrievalEngine` 内部用于候选评分，不改变 `RetrievalRequest` 对外契约。
   - `_score_candidate_edge()` 拆为图路径分、显式实体命中、文本语义相关和结构上下文分。
   - 有明确人物 / 地点命中时，对无关玩家背景关键词加分限幅，避免高 clarity 背景边压过当前点名实体。
   - 保持 `_find_start_nodes()` 不变；被点名但非参与者的人物不会被加入图起点。
   - `_rerank_node_data()` 对已经明确命中的 relationship / person 节点做有限补偿，避免路径命中后在最终上下文中被 person 惩罚挤掉。
4. `backend/tests/test_memory_edge_semantics.py`
   - 新增低 bond 核心人物认知下限、高 bond 小幅提升、规则不按具体人物分支的回归测试。
5. `backend/tests/test_conversation_memory_routing.py`
   - 新增竞争图测试：高 clarity 玩家背景事件、商店街背景事件和千早 relationship 同时竞争。
   - 验证“你知道千早在哪里吗”能选中千早关系边、包含千早节点、且不依赖向量兜底。
   - 验证“喫茶店最近怎么样”仍优先命中玩家喫茶店背景。
6. `docs/Workstreams/Memory/README.md`
   - 将专项草案状态更新为已落档 plan / execution。

## 诊断与控制钩子

本轮没有新增外显诊断字段。现有 `RetrievalResult` 与 `aisc_debug.conversation_retrieval_snapshot` 已覆盖验收所需字段：

1. `start_node_ids`
2. `selected_edge_ids`
3. `retrieved_node_ids`
4. `vector_query_preview`
5. `vector_fallback_used`
6. `failure_reason`

因此没有修改 Unity 诊断 DTO、MCP action 或诊断 README。内部评分中临时记录的 `explicit_entity_match_score` / `semantic_relevance_score` 只保留在候选元数据中供本地排序和 rerank 使用，不作为外部诊断契约。

## 验证

1. 红测阶段：
   - `python -m unittest backend.tests.test_memory_edge_semantics backend.tests.test_conversation_memory_routing -v`
   - 结果：新增边语义测试因 `initial_relationship_clarity` 尚不存在报错；竞争图测试中 `edge_kujo_chihaya` 未进入 `selected_edge_ids`，实际选中 `edge_player_cafe` 与 `edge_city_background`。
2. 修复后目标验证：
   - `python -m unittest backend.tests.test_memory_edge_semantics backend.tests.test_conversation_memory_routing -v`
   - 结果：9 项通过。
3. 后端全量验证：
   - `python -m unittest discover -s backend/tests -v`
   - 结果：53 项通过。
4. Unity Play Mode 现场诊断追加验证：
   - 使用 `aisc_debug.conversation_retrieval_snapshot` 抓取玩家问“你知道千早在哪吗”的当前状态。
   - 观察到初始 clarity 已修复：`edge_rel_kujo_chihaya` 为 `clarity_ab=0.736 / clarity_ba=0.617`。
   - 观察到路由仍不理想：`selected_edge_ids` 只包含两条玩家背景边，`vector_fallback_used=true`；原因是近期 NPC 回复中的“小李 / 喫茶店”被当成与当前玩家发言“千早”同权的显式实体。
   - 追加修正：实体匹配区分 `query_match` 与 `context_match`，当前玩家发言命中给强权重，近期对白 / 摘要命中只作弱提示；当前发言强命中的 top1 明确领先时，本地路由直接接管，避免再次交给 LLM 摇摆。
   - 追加回归测试：`test_named_person_question_beats_high_clarity_player_background_edges` 改为包含“喫茶店那边的小李？”的真实同形上下文；新增 `test_query_entity_top_candidate_uses_local_route_despite_background_tie`。
   - 追加目标验证：`python -m unittest backend.tests.test_memory_edge_semantics backend.tests.test_conversation_memory_routing -v`，10 项通过。
   - 追加全量验证：`python -m unittest discover -s backend/tests -v`，54 项通过。
   - 只读复算真实运行库候选排序：`edge_rel_kujo_chihaya` 成为 top1，`local_score=4.625`；最近对白中的玩家 / 喫茶店仅为弱上下文，玩家背景边降为 `3.655 / 3.42`；`can_use_local_route=true`。

`python -m pytest ...` 未执行成功：当前 `python` 环境未安装 `pytest`。项目既有执行记录也以标准库 `unittest` 为主，因此本轮改用等价覆盖的 `unittest` 命令验证。

未修改 Unity 资产、DTO、诊断 action 或运行时 C# 逻辑。已使用 Play Mode 下的 `aisc_debug` 做只读诊断；真正重新发问后的运行时效果需要后端服务加载最新 Python 代码后再由 Unity 触发一轮新检索确认。

## 文档与边界回查

1. `docs/Workstreams/Memory/README.md` 已更新专项状态。
2. `docs/Workstreams/Dialogue/README.md` 仍准确表达：玩家正式对话每轮刷新图检索，图起点保持既有策略，不做话题实体定向起点或话题人物关系预查；无需修改。
3. `docs/DecisionRecords/ADR-0001-memory-v07-light-graph.md` 边界未改变：图仍负责联想路径，向量层仍只做语义内容和兜底。
4. 旧数据库历史 relationship 边未迁移；冷启动 clarity 修复只影响新建图。手动复测如使用旧存档，需要新开局或显式重建初始图。

## 未完成项

1. 未做旧库批量迁移。
2. 未做真实 Unity Play Mode 手动验收。
