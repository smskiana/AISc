> 设计方案: [2026-07-17_LLM检索想法向量路由修复_plan.md](2026-07-17_LLM检索想法向量路由修复_plan.md)

# LLM 检索想法、单次向量路由与最终原子条目选择修复执行记录

## 实际改动

1. 新增 `retrieval_query.py`：从校准后的方向生成唯一 `RetrievalQueryPlan`。embedding query 固定为原问题、检索想法和至多一条确定性选出的相关对白；场景、摘要、玩家背景和近期记忆列表不再进入 query。空、超长、越权稳定实体和新增精确时间分别以稳定原因回退原问题。
2. 新增 `retrieval_context.py`：将图候选与单次向量命中按 node ID 去重，使用语义相似度、图路径、明确实体、时效、importance、类型先验六分量选择完整条目。类型先验配置化且硬限制为 0.05；`person`、`identity`、`place` 使用中性渲染，字符不足时整条淘汰。
3. 扩展 `memory_direction` 的 response/system contract、`RetrievalDirection` 与 `DirectionResolver`：一次既有 LLM 调用可返回 `retrieval_query` 和 `query_constraints`；当前问题中的人物/地点由本地方向权威保留，定位/身份等明确语义会校准 LLM 的泛化合法 JSON。
4. `RetrievalEngine` 仅编排 provider、query planner、一次 ANN、图检索和 context assembler；旧 facade 内重排/重建实现不再参与正式路径。LanceDB adapter 把归一化 BGE 的默认平方 L2 `_distance` 明确转换为 0..1 similarity。
5. 三个 mode 的 local 深度改为 7 / 5 / 9，完全 LLM 路由 hop 与调用预算改为 7 / 5 / 7；未调整 beam、frontier、邻边或总展开边预算。
6. 扩展 trace、会话诊断、Unity DTO 和 EditMode 测试，提供原问题、检索想法、query 来源、近期对白选择、单次向量命中、图候选、最终评分分量、淘汰原因和条目字符量。
7. 新增 query/context 测试、五层固定图深度回归，并扩展九组合离线评估输出。

## 验证证据

1. `python -m pytest backend/tests -q`：83 passed，3 subtests passed。
2. `python backend/scripts/evaluate_deep_retrieval.py`：九组 mode / strategy 均完成；`local_only` 为 0 次方向 LLM 且 1 次向量，`llm_guided_local` 为 1 次方向 LLM 且 1 次向量，`llm_full_route` 为 0 次向量。输出已包含 query 来源、最终评分分量、淘汰原因和字符量。
3. 固定链图测试证明本地与完全 LLM 路由均可到达第 5 层，覆盖旧上限之外、新上限以内的路径；既有总边预算停止语义仍由 `edge_budget_exhausted` / `budget_exhausted` 保留。
4. Unity MCP：`DiagnosticModels.cs` 与 `AiscDiagnosticsTests.cs` 静态校验均为 0 error；EditMode `AiscDiagnosticsTests` 10 / 10 通过。
5. 只读真实运行样本通过 `POST /api/memory/retrieval_probe` 验证，trace 为 `retrieval_9ee6bb08f6d9`。该 probe 禁用 clarity 恢复和持久检索日志。`aisc_debug.memory_retrieval_snapshot` 显示：
   - `recall_intent=locate_person`、`query_constraints=[person_location]`，有 `direction_semantic_calibrated`；
   - `embedding_query` 仅含当前问题和“千早的位置”，不含 `flower_shop.counter`；
   - `vector_query_count=1`；
   - 千早人物节点和千早身份节点进入 `final_entries`，final IDs 与最终上下文一致。

## 文档回写

- 更新 Memory / Dialogue Workstream、Memory / Dialogue / config / tests / Diagnostics README。
- 更新对应错误预防明细的状态为已修复。
- 更新 Memory 执行证据入口并移除该事项的待执行状态。

## 未完成项与边界

1. 未注入 `npc_states.current_location`，也未让向量命中成为图起点或直接答案；这符合方案边界。
2. Unity Console 在本轮验证前后仍有 41 条既有 `Import Error Code:(4)` 与 `The referenced script (Unknown) on this Behaviour is missing!`，不属于本次检索/诊断 DTO 编译错误。为避免掩盖现有项目错误，未清空 Console，也未修改无关场景资产；因此“全项目 Console 0 Error”未作为本次验证结论。
3. Unity MCP 暴露的 `aisc_control` 动态 schema 当前只接受 `action`，尽管项目 custom-tools resource 与 C# 参数类声明了 probe 的 query / NPC 参数；带参数调用被 MCP schema 拒绝。仍已调用无参数 `run_memory_retrieval_probe` 验证控制入口，并通过同一正式只读 probe HTTP seam 传入目标查询后，再以 `aisc_debug` 读取完整 trace。该 MCP schema 刷新问题需独立排查，不能以运行时代码绕过。
4. 未创建 SQLite / LanceDB 副本执行 P50 / P95 对比；本轮只读 probe 不写正式数据，但性能对比仍需在独立测试数据副本中补做。
