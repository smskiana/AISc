> 执行案：[2026-07-21_记忆路由零LLM确定性查询切换_plan.md](2026-07-21_记忆路由零LLM确定性查询切换_plan.md)
>
> 独立测试记录（待测试会话创建）：[2026-07-21_记忆路由零LLM确定性查询切换_test.md](2026-07-21_记忆路由零LLM确定性查询切换_test.md)

# 记忆路由零 LLM 确定性查询切换 - 执行记录

## 1. 执行结论

已按唯一 plan 完成实现，当前结论为：**实现完成，待独立测试**。

生产配置的玩家、NPC 与午夜检索均为 `local_only + [local]`；生产 provider 注册表只保留 `general_llm` 与 `local`，不会构建、预热或常驻 R3 v2 worker。R3 v2、通用 LLM 和三种公开策略的实现能力未删除，相关回归通过显式测试 payload 保留。

本执行会话未创建 `_test.md`，也未进行 Unity Player 真实对话墙钟验收；复杂任务整体完成状态必须由后续独立测试记录决定。

## 2. 实际修改

1. `backend/config/memory_retrieval.yaml`
   - 默认 chain 改为 `[local]`，删除生产 `r3_v2` 注册块。
   - `player_dialogue` 改为 `local_only + [local]`；NPC 与午夜保持相同本地口径。
   - 检索预算、query、scoring 和公开 strategy 能力未改变。
2. 后端回归
   - 默认 policy 锁定三 mode 本地策略、生产 provider 集合和原预算。
   - R3 path/env/hash 校验、三 provider builder 和隔离 factory 改用显式测试 payload。
   - 玩家默认 trace 锁定 `direction_source=local`、provider `not_applicable`、方向/路由模型调用为 0，并继续验证原问题与一条相关近期对白进入唯一 query。
   - local runtime evaluator 按 `not_applicable` 口径不再统计 adopted provider；新增生产 runtime 无专项 worker、空 health、空 warmup 回归。
3. 文档
   - Memory 代码 README、Workstream、实验草案和 AIChanges 索引均更新为 C 已实现、R3/LongCat 未配置但能力保留。
4. 明确未改
   - 未修改 `RetrievalEngine`、`GameRuntime`、`DirectionProviderRuntime`、`RetrievalQueryPlanner`、trace builder、schema、Unity 资产或模型实现。

## 3. 实现期最低门禁

### 3.1 聚焦 pytest

使用与项目现有 pytest 相同的 `C:/Users/HP/Documents/yvyan` Python 环境，并显式设置项目根 `PYTHONPATH`：

```text
pytest backend/tests/test_retrieval_policy.py
       backend/tests/test_retrieval_query.py
       backend/tests/test_retrieval_direction.py
       backend/tests/test_route_specialist_provider.py
       backend/tests/test_conversation_memory_routing.py
       backend/tests/test_route_runtime_evaluator.py
```

结果：`32 passed, 32 warnings`。warnings 均为 LanceDB `table_names()` deprecation，无业务失败。

### 3.2 九组合离线回归

运行 `backend/scripts/evaluate_deep_retrieval.py`，三 mode × 三 strategy 共 9 组均正常输出，`failure_reason=none`。所有 `local_only` 组合均为 `llm_calls=0`、`vector_queries=1`、`retrieval_query_source=local`；显式 `llm_guided_local` / `llm_full_route` 能力仍可执行。

### 3.3 local 隔离 runtime 评估

使用批准 factory 与脱敏 corpus：

```text
evaluate_route_runtime.py
  --engine-factory backend.tests.route_runtime_isolated_factory:create_engine
  --provider local
  --corpus backend/tests/fixtures/route_runtime_corpus.jsonl
  --output F:/AIScLocalArtifacts/memory-route/artifacts/zero-llm-local-runtime-20260721.json
```

结构化结果：`case_count=2`、`expected_hit_rate=1.0`、`forbidden_hit_count=0`、`adopted_provider_count=0`、`side_effect_free=true`、`warmup={}`。

产物 SHA-256：`d82cb75fb98a5cc1110e271143497df5520d790b6df0d494475b14adc0ef136b`。

## 4. 执行中问题

1. PATH 中 `python` 缺少 PyYAML，而 `pytest` 使用 `yvyan` 环境；脚本改用后者对应解释器，未安装或修改依赖。
2. 初轮测试发现两处旧默认耦合：生产配置取 R3 block、local evaluator 统计 adopted provider。均按 plan 改为显式 R3 payload及纯 local `not_applicable` 口径。
3. 本轮发现并立即修正一次测试 helper 的机械替换误命中，最终聚焦门禁已覆盖该路径。

## 5. 索引与后续

执行前后均刷新 codebase-memory 项目 `AISc`，并同步 `docs/AIChanges/codebase-memory-mcp_更新.md`。本轮不改变 ADR、Roadmap 或系统边界。

后续必须在独立测试会话读取本 execution 与 plan，完成真实启动无专项环境变量、生产 health/warmup、Unity Player 首轮和后续轮墙钟及 p95 等独立验收，再创建互链 `_test.md`。
