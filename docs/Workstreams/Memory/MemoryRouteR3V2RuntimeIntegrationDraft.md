# R3 v2 记忆路由运行时接入草案

## 1. 文档定位

本文只定义 `Qwen3-0.6B + Route LoRA R3 v2` 的运行时接入边界、默认选择、回退、诊断和验收口径，不直接授权实现。

训练、离线评估和产物冻结仍以以下记录为证据：

1. `docs/AIChanges/Memory/2026-07-20_记忆路由专项模型部署与训练_plan.md`
2. `docs/AIChanges/Memory/2026-07-20_记忆路由专项模型部署与训练_execution.md`
3. `docs/AIChanges/Memory/2026-07-20_记忆路由专项模型部署与训练_test.md`

基于当前代码复核后的唯一 implementation plan 为：

4. `docs/AIChanges/Memory/2026-07-20_R3v2记忆路由运行时接入_plan.md`

本文遵守 ADR-0001：不扩张轻量图模型，不改变“图负责联想路径、向量层负责语义内容与兜底”的边界。

## 2. 需求解释

本轮把“默认使用 R3 v2”解释为：

1. R3 v2 成为需要方向解析时的默认 `DirectionProvider`。
2. 现有三种检索策略 `local_only`、`llm_guided_local`、`llm_full_route` 全部保留。
3. `local_only` 仍直接使用本地方向，不加载或调用 R3 v2。
4. `llm_guided_local` 默认使用 R3 v2 生成 `RetrievalDirection`，后续仍由现有本地图搜索、向量兜底和最终重排完成检索。
5. 原 `llm_guided_local + LlmDirectionProvider` 实现完整保留，可通过 `[general_llm, local]` 恢复原行为，不降级为仅供回退使用的兼容代码。
6. `llm_full_route` 保留现有逐跳通用 LLM 路由；R3 v2 不替代逐跳边选择。
7. 按当前 mode 配置，玩家对话默认进入 `llm_guided_local + R3 v2`；NPC-NPC 与夜间仍保持 `local_only`，除非后续单独调整 mode 策略。

因此，R3 v2 只是 `llm_guided_local` 新的默认方向来源，不删除、不改写原通用 LLM 方向实现，也不替换整套图检索或把所有业务 mode 强制改成模型路由。

## 3. 已冻结候选

默认候选固定为：

| 项目 | 冻结值 |
|---|---|
| provider ID | `r3_v2` |
| 底模 | `Qwen/Qwen3-0.6B` |
| revision / tokenizer revision | `c1899de289a04d12100db370d81485cdf75e47ca` |
| Adapter | `route-lora-r3-v2-approved-480/adapter` |
| Adapter SHA-256 | `cd2676f7f64f28a351fb35b2d2d76fa01b30662a509bf7bbddcced6f9cf92b8d` |
| 量化 | NF4，BF16 compute，double quant |
| 解码 | deterministic、`do_sample=false`、thinking 关闭 |
| schema | 现有 `RetrievalDirection` / route dataset schema v1 |

R3 v3 不进入默认配置。当前独立证据显示其总体字段质量与 v2 持平，但尾延迟更差，没有形成替换收益。

模型、Adapter、Hugging Face 缓存和 Python venv 继续位于项目外，不提交 Git。仓库配置只保存稳定 ID、revision、hash、环境变量名和行为参数，不保存机器绝对路径。

## 4. 模块与 seam

### 4.1 保持调用 seam 不变

调用方继续只依赖现有接口：

```text
DirectionProvider.provide(request, context) -> DirectionResolution
```

`RetrievalEngine` 仍是检索 facade，但不负责模型加载、进程管理、prompt 编码、JSON 解析或 provider 回退编排。

### 4.2 新增深模块

建议新增三个职责明确的模块：

1. `SpecialistRouteCodec`
   - 生产与训练共同使用同一 system prompt、输入序列化、thinking 关闭规则和严格 JSON 解析。
   - 输出只允许构造 `RetrievalDirection`，不得输出节点 ID、边 ID、回答文本或推理过程。
   - 解决训练模板与运行模板漂移，不允许运行时代码反向依赖 `backend/training/`。

2. `LocalSpecialistRuntimeAdapter`
   - 管理一个常驻 Python 3.11 worker、共享底模加载、任务 Adapter 注册/切换、健康状态、单请求推理、超时、终止和有界重启。
   - worker 使用现有训练 venv 的 `torch / transformers / peft / bitsandbytes` 兼容矩阵；正式后端进程不直接导入这些依赖。
   - worker stdin/stdout 只传 versioned JSONL，日志只写 stderr，避免协议与日志混流。
   - 首轮只常驻一份冻结的 `Qwen3-0.6B` NF4 底模，分别注册 R3 v2 Route Adapter 和独立 Merge Adapter；两个任务共用 runtime，不共用 codec、schema、validator 或失败策略。

3. `ChainedDirectionProvider`
   - 按配置顺序执行任意 provider 列表，第一个成功结果生效。
   - provider 失败统一转换为稳定失败原因，调用方不写 R3 v2 专用 if/else。
   - 默认链为 `r3_v2 -> local`；原 `general_llm -> local` 链继续作为正式可选实现，也可把 `general_llm` 显式插入其他回退链。

`R3V2DirectionProvider` 只负责把 `DirectionProvider` seam 适配到 codec 和共享 runtime adapter，不自行复制校准、mention resolver 或本地图搜索逻辑。

## 5. 为什么使用常驻 worker

R3 v2 的训练环境是独立 Python 3.11 venv，正式后端环境没有冻结同一套 GPU 推理依赖。直接把模型塞入 `RetrievalEngine` 或正式后端进程会同时产生依赖冲突、无法硬超时、显存生命周期不清和 facade 继续增重的问题。

常驻 worker 提供以下隔离：

1. 底模只加载一次，避免每轮冷启动，也避免路由和融合各常驻一份相同 0.6B 权重。
2. worker 崩溃或推理卡死时可以终止并在冷却后重启，不拖垮正式后端。
3. 正式后端只持有小型 Adapter interface，可用 fake worker 做确定性测试。
4. 后续替换 Adapter 或迁移 C# 时，不改变 `DirectionProvider` seam。

本轮不引入网络端口、HTTP 服务、模型服务器或多 worker 池。worker 仅是后端拥有的本机子进程，单 worker、单在途请求、队列上限 1；Route/ Merge Adapter 切换在 worker 内串行，融合只在无玩家路由请求时调度，并发超限时 route 按 provider chain 回退、merge 直接 skip，不无限排队。

## 6. 请求流程

```text
RetrievalEngine
  -> 根据 mode 取得 RetrievalStrategy
  -> local_only: LocalDirectionProvider
  -> llm_full_route: 保持现有逐跳 LLM 路由
  -> llm_guided_local:
       默认 ChainedDirectionProvider[r3_v2, local]
         -> R3 v2 编码、推理和严格 JSON/schema 校验
       或原 ChainedDirectionProvider[general_llm, local]
         -> 现有 LlmDirectionProvider 通用 LLM 方向解析
       -> DirectionResolver 本地校准与 mention 解析
       -> DirectedDeepRetriever
       -> 现有单次向量查询、兜底与最终重排
```

provider 选择和回退链在单次请求开始时冻结，中途不得因配置变化切换。R3 v2 成功只计为一次方向模型调用，不得增加 embedding、ANN 或 clarity 恢复次数。

## 7. 配置草案

共享 runtime 同时服务路由和融合，不归 `memory_retrieval.yaml` 单独所有。建议新增严格校验的 `local_specialist_runtime.yaml` 保存底模和任务 Adapter 注册表；`memory_retrieval.yaml` 升级为 version 2，只增加方向 provider 引用。各 mode 继续保留现有 strategy，只有需要时覆盖 provider chain。

`backend/config/local_specialist_runtime.yaml`：

```yaml
version: 2
local_specialist_runtime:
  runtime_id: qwen3_0_6b_shared
  model_id: Qwen/Qwen3-0.6B
  revision: c1899de289a04d12100db370d81485cdf75e47ca
  python_env: MEMORY_SPECIALIST_PYTHON
  hf_home_env: HF_HOME
  adapters:
    route_r3_v2:
      adapter_id: route-lora-r3-v2-approved-480
      adapter_path_env: MEMORY_ROUTE_R3_V2_ADAPTER
      adapter_sha256: cd2676f7f64f28a351fb35b2d2d76fa01b30662a509bf7bbddcced6f9cf92b8d
    memory_merge:
      adapter_id: qwen3_0_6b_merge
      adapter_path_env: MEMORY_MERGE_ADAPTER
      adapter_sha256: <训练后冻结>
```

`backend/config/memory_retrieval.yaml`：

```yaml
version: 2
direction_providers:
  default_chain: [r3_v2, local]
  providers:
    r3_v2:
      kind: subprocess_specialist
      runtime_id: qwen3_0_6b_shared
      adapter: route_r3_v2
      timeout_ms: 16000
      max_new_tokens: 384
      restart_cooldown_ms: 5000
    general_llm:
      kind: general_llm
    local:
      kind: local
modes:
  player_dialogue:
    strategy: llm_guided_local
    direction_chain: [r3_v2, local]
    # 其余现有预算保持不变
  npc_dialogue:
    strategy: local_only
  nightly_impression:
    strategy: local_only
```

需要恢复接入前的玩家引导深搜时，只修改 provider chain，不修改 strategy 或检索预算：

```yaml
modes:
  player_dialogue:
    strategy: llm_guided_local
    direction_chain: [general_llm, local]
```

`16000ms` 是依据现有关闭 thinking 的 R3 v2 独立 p95 `13188.404ms` 加有界余量形成的初始值，不是长期性能目标。若真实运行 p95 超出该值，不应无界提高超时；应保留本地回退并单独优化推理。

配置规则：

1. 未知 provider、重复 provider、空链、缺少 local 终点、非法 timeout 或 hash 格式在启动校验时失败。
2. 本地模型路径只从环境变量解析；配置和诊断不得输出私有目录的完整路径。
3. `local_only` 忽略方向链；`llm_full_route` 不把 R3 v2 误记为逐跳路由调用。
4. `[general_llm, local]` 必须与接入前的 `llm_guided_local` 行为等价，包括 Prompt、校准、失败原因、模型调用计数和检索预算。
5. 默认链不包含 `general_llm`，避免 R3 v2 超时后再叠加一次十秒级外部调用；需要质量优先时可显式配置 `[r3_v2, general_llm, local]`。
6. 第一版不做配置热加载，修改后重启生效，并在诊断中显示已加载的 config version 和 provider chain。
7. Route 与 Merge Adapter 必须引用同一 `runtime_id`、底模 revision、tokenizer 和量化口径；共享的是底模 runtime，不是任务 Adapter。

## 8. 生命周期与失败收口

### 8.1 启动

1. 后端启动时校验 provider 配置、worker Python、Adapter manifest、revision 和 SHA-256。
2. worker 异步预热；预热失败不得阻止后端 READY，provider 标记为 unavailable，正式请求直接回退到 local。
3. worker ready 后才允许接收推理请求；不得让首个玩家请求隐式承担完整模型加载。

### 8.2 稳定失败原因

至少区分：

```text
specialist_unavailable
specialist_manifest_mismatch
specialist_load_failed
specialist_busy
specialist_timeout
specialist_worker_exited
specialist_invalid_json
specialist_schema_invalid
specialist_semantic_rejected
specialist_fallback_local
specialist_fallback_general_llm
```

超时、worker 退出和协议损坏必须使当前请求立刻回退，并使 worker 进入有界重启冷却。非法 JSON、schema 错误或语义拒绝只拒绝本次输出，不让未经校准的方向进入检索。

第一版不引入模型 confidence 字段。现有 R3 v2 没有经过可用的置信度校准，不能用自报 confidence 决定业务事实。

## 9. 诊断契约

在现有 retrieval trace 上补充结构化字段：

1. `direction_provider_requested`
2. `direction_provider_adopted`
3. `direction_provider_chain`
4. `direction_model_id`
5. `direction_model_revision`
6. `direction_adapter_id`
7. `direction_schema_version`
8. `direction_inference_ms`
9. `direction_queue_ms`
10. `direction_fallback_reasons`
11. `direction_worker_state`
12. `direction_model_call_count`

现有 `llm_route_calls` 继续只表示完全 LLM 逐跳路由调用，不能混入 R3 v2 方向调用。日志与 Unity 诊断只保存字段数量、枚举摘要、稳定失败原因和关联 trace ID，不保存完整对白、模型原始输出或未授权记忆文本。

## 10. 预计实现边界

后续实施 plan 至少会涉及以下范围，执行前必须按最新代码复核名称：

### 10.1 新增

```text
backend/src/memory/route_specialist_contract.py
backend/src/memory/route_specialist_provider.py
backend/src/memory/local_specialist_runtime.py
backend/src/memory/local_specialist_worker.py
backend/config/local_specialist_runtime.yaml
backend/tests/test_route_specialist_contract.py
backend/tests/test_route_specialist_provider.py
backend/tests/test_local_specialist_runtime.py
```

### 10.2 修改

```text
backend/src/memory/retrieval.py
backend/src/memory/retrieval_policy.py
backend/src/memory/retrieval_contracts.py
backend/config/memory_retrieval.yaml
backend/training/memory_route/common.py
backend/tests/test_retrieval_policy.py
backend/tests/test_retrieval_direction.py
backend/tests/test_retrieval_pipeline.py 或现有等价集成测试
backend/src/memory/README.md
backend/training/memory_route/README.md
docs/Workstreams/Memory/README.md
```

`RetrievalEngine` 只接受已组装的 provider registry 或 chain，不在 `_retrieve_result` 中继续新增多个模型专用分支。若代码级分析发现必须继续扩大该类职责，实施前需按项目规则取得“减重”指令。

## 11. 测试与验收草案

按测试工具 Workstream，最低充分组合为后端聚焦 pytest + 离线专项模型评估 + 隔离检索 probe；不涉及 Unity 场景、Prefab 或 SerializeField。

### 11.1 实现会话最低门禁

1. codec golden test：训练与运行时对相同输入生成完全一致的 prompt、thinking 关闭参数和 schema。
2. provider chain test：R3 v2 成功、不可用、busy、超时、worker 退出、非法 JSON、schema 错误均采用预期 provider，且 local 终点不抛异常。
3. policy test：三种既有 strategy 全部可配置，玩家默认 chain 为 `[r3_v2, local]`，原 `[general_llm, local]` 可独立选择，NPC 与夜间默认仍为 local。
4. worker protocol test：版本、request ID、stdout/stderr 隔离、单在途、有界重启和 Route/ Merge Adapter 串行切换成立，底模加载次数保持为 1。
5. retrieval regression：每轮方向模型调用不超过 1，embedding/ANN 次数不增加，clarity 与副作用口径不变。
6. 启动 smoke：模型缺失、hash 错误和 CUDA 不可用均不阻止后端 READY，并通过 trace 显示 local fallback。

### 11.2 独立测试会话

1. 使用真实 R3 v2 Adapter 重跑冻结字段集，schema 合法率、明确实体召回、未知实体和字段准确率不得低于当前独立基线。
2. 使用带 `expected_node_ids`、权限结果和隔离 SQLite/LanceDB 的 corpus，对相同输入比较 `r3_v2`、`general_llm`、`local` 的检索命中与越权结果。
3. 玩家默认路径必须证明 `direction_provider_adopted=r3_v2`；故障注入路径必须证明采用 local 且最终检索不中断。
4. 在 RTX 4060 Laptop GPU 同等条件下，预热后 p95 不高于当前 R3 v2 独立 p95 加 20%；冷启动、常驻显存、峰值显存和端到端对话等待分别记录。
5. `local_only`、原 `llm_guided_local + general_llm`、新 `llm_guided_local + r3_v2`、`llm_full_route` 都要独立验收；原九组合离线评估不得回退。
6. 所有测试使用隔离数据，不修改正式存档、clarity、运行配置或模型产物。

当前训练 test 已明确缺少检索级 `expected_node_ids`、权限复核和隔离 engine factory。后续不能仅凭 12 条字段级结果宣布默认接入整体通过；这些缺口必须在独立测试会话补齐。

## 12. 风险与停止条件

1. R3 v2 当前预热后仍是约 11 至 13 秒级推理，虽然优于现有外部 LLM 样本平均墙钟，但可能不满足最终对话体验；不得把模型接入成功等同于体验达标。
2. worker 进程增加生命周期和诊断复杂度，但这是隔离正式后端与训练依赖、实现可终止超时的必要成本；第一版不扩大为通用模型平台。
3. Adapter、tokenizer、system prompt、schema、量化或 generation 参数任一变化都视为新模型 revision，必须重新冻结和验收，不能继续沿用 `r3_v2` ID。
4. 若真实隔离检索显示知识越权、相关节点命中低于基线或回退后重复 ANN，不得切为默认。
5. 若 worker 无法稳定退出、超时无法收口或后端 READY 依赖模型成功加载，停止实施并回到方案会话调整边界。
6. 共享底模降低常驻显存，但两个任务仍会竞争同一推理队列；若午夜融合阻塞玩家路由，必须优先保证 route，并跳过或延后 merge。

## 13. 方案确认后的阶段划分

当前代码复核后的唯一 implementation plan 已建立。预计实施会修改超过 3 个文件并新增超过 2 个文件，必须按项目规则分为 plan、execution、test 三个独立对话：

1. plan：冻结配置 schema、模块名称、worker 协议、文件清单和验收命令。
2. execution：以该 plan 为唯一来源实现，更新 codebase-memory，完成最低门禁后只得出“实现完成，待独立测试”。
3. test：补齐真实 Adapter、隔离检索、权限、故障注入和性能证据，写互链 test record 后才能认定整体完成。

## 14. 相关入口

1. `docs/Workstreams/Memory/README.md`
2. `docs/Workstreams/Memory/MemoryRoutingSpecialistModelSwitchDraft.md`
3. `docs/DecisionRecords/ADR-0001-memory-v07-light-graph.md`
4. `backend/src/memory/retrieval_contracts.py`
5. `backend/src/memory/retrieval_direction.py`
6. `backend/src/memory/retrieval.py`
7. `backend/config/memory_retrieval.yaml`
8. `backend/training/memory_route/README.md`
9. `docs/Workstreams/Memory/MemoryMergeSpecialistModelSwitchDraft.md`
