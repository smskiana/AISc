> 执行案：[2026-07-20_R3v2记忆路由运行时接入_plan.md](2026-07-20_R3v2记忆路由运行时接入_plan.md)
>
> 独立测试记录：[2026-07-20_R3v2记忆路由运行时接入_test.md](2026-07-20_R3v2记忆路由运行时接入_test.md)

# R3 v2 记忆路由运行时接入 - 执行记录

## 1. 执行结论

已按唯一 plan 完成代码、配置、聚焦测试、真实 worker smoke、运行时评估入口和相关文档修改。`RetrievalEngine` 已移除请求内具体 provider 构造，`GameRuntime` 只持有唯一 `DirectionProviderRuntime` 并在存档恢复时复用；实现结论为“实现完成，待独立测试”。

本记录不替代独立 test。真实隔离图质量、权限、GPU p50/p95/p99、显存、全故障矩阵和 Unity 实际对话等待仍须在独立测试会话验收。

## 2. 实际改动

1. `memory_retrieval.yaml` 升级为严格 version 2，注册 `r3_v2 / general_llm / local`，玩家默认 `[r3_v2, local]`，NPC 与午夜为 `[local]`；重复 key、未知字段、路径值、非法 hash、chain 非 local 终点均启动失败。
2. `route_specialist_contract.py` 统一 schema v1 input、方向字段、system prompt、紧凑 messages、严格 JSON/schema/枚举/长度/ID/mention 来源校验；训练 `common.py` 改为窄 re-export。
3. `route_specialist_worker.py` 实现轻量父进程 adapter、延迟重依赖 import、版本化 JSONL、容量 1、busy/timeout/EOF/坏协议、冷却、一次后台重启和 shutdown/terminate/kill 有界关闭。
4. worker 启动前校验 Python、Adapter manifest、底模和 tokenizer revision、64 位 SHA-256 与 HF cache；机器路径仅来自环境变量，不进入配置或诊断。
5. `route_specialist_provider.py` 以 builder mapping 注册三种 provider；chain 丢弃失败 provider 的内部 fallback，再由正式 local 终点生成方向，并保留有界 attempt 诊断。
6. `RetrievalEngine` 注入 provider runtime，只根据 strategy 选择 override / local / policy chain；`llm_full_route` 不参与 R3，方向模型不污染 `llm_route_calls`。
7. trace 新增请求/采用 provider、chain、冻结模型身份、schema、耗时、queue、稳定回退、worker 状态和模型调用次数；不保存 Prompt、完整输入、原始输出或绝对路径。
8. `GameRuntime` 同步校验配置和装配 runtime，后台预热不阻塞 READY；stop 在取消业务任务后关闭 worker，存档恢复只重建 engine/向量句柄并复用 runtime。
9. 新增 `evaluate_route_runtime.py`，只接受显式隔离声明的 `module:function` factory，以及带允许/拒绝节点预期的 UTF-8 JSONL，并只调用 `probe()`。

## 3. 实现期门禁

测试工具按 `docs/Workstreams/TestingAndDiagnostics/README.md` 选择 `backend/tests` 聚焦 pytest、`evaluate_deep_retrieval.py` 和真实训练 venv worker smoke。系统 Python 3.11 缺 pytest，因此自动化测试使用现有 `C:/Users/HP/Documents/yvyan/python.exe`；真实模型只使用冻结训练 venv 和显式 `HF_HOME`。

1. plan 最低聚焦集合加检索集成：54 passed。
2. 隔离运行时 evaluator：3 passed。
3. Application 既有生命周期回归 `test_pause_sync.py`：3 passed。
4. 后续 policy/worker/provider 增量门禁：19 passed；重复 key、冻结 hash、UTF-8 stdio 和一次重启均覆盖。
5. `evaluate_deep_retrieval.py`：九种 mode / strategy 组合完成；非完全路由保持单次向量查询，完全路由为 0 次向量查询。
6. 静态编译：所有新增/修改 Python 模块通过 `py_compile`；父进程只读 import 证明未加载 `torch / transformers / peft / bitsandbytes`。
7. 真实 worker smoke：批准 Adapter hash 与配置一致；worker READY 后中文请求成功采用 `r3_v2`，`recall_intent=locate_person`，模型调用 1 次，随后状态进入 `closed`。
8. 完整 `backend/tests`：142 passed、3 subtests passed、3 failed。失败均位于未修改的 `test_schedule_candidates.py`，其 `_Catalog` 夹具缺少现有 `task_runtime_metadata()`，与本次 Memory 调用链无关，未越界修改。
9. `git diff --check`：通过。
10. 最终合并聚焦门禁（policy、方向、query、context、deep retrieval、codec、provider、worker、runtime evaluator、训练契约、对话检索和 Application 生命周期）：62 passed。

## 4. 实现中修正的问题

1. 原 plan 的 63 位 Adapter hash 已在独立方案会话按实物复算纠正；本会话重新复算 64 位小写值后才写入配置。
2. 首次真实 warmup 暴露“启动完成事件错误复用推理 timeout”，已拆分 startup 事件并使用独立有界加载窗口。
3. 中文真实推理暴露 Windows 子进程标准流仍沿用系统代码页，产生孤立 surrogate 并伪装成 tokenizer 类型错误；worker 入口现显式把三条标准流配置为 UTF-8，错误预防明细见 `docs/DesignDocs/errors/2026-07-21_windows_subprocess_jsonl_stdio_encoding.md`。

## 5. 文档、索引与未完成项

已更新 Memory / training / scripts README、Memory Workstream、错误预防索引和本目录索引；未修改 Roadmap、ADR、Unity 资产、协议 DTO、存档 schema、图算法或模型产物。

codebase-memory 对当前工作树建立了 `AISc_r3v2_runtime_20260721` moderate 验证索引（6666 nodes / 22233 edges，actual=expected），五个新增关键符号均可检索。canonical `AISc` 因同一 HEAD 缓存未被 moderate/fast 替换，full 又触发 indexing worker `exit_nonzero`；旧 canonical artifact 未伪报为新鲜，状态与后续刷新要求已写入 `docs/AIChanges/codebase-memory-mcp_更新.md`。

独立测试会话必须按 plan 第 11 节创建 test record；在该记录通过前，不得宣称 R3 v2 默认运行时接入整体完成。

## 6. 2026-07-21 独立测试失败后修复

### 6.1 失败证据与根因

按独立 test 的结构化证据，只处理原主题内三个缺口：

1. 冻结 NF4 worker 未在模型加载前检查 CUDA，`device_map=auto` 可在禁用 GPU 时走 CPU 并错误发 READY，直到首次推理超时。
2. `evaluate_route_runtime.py` 只有 fake probe 自测，没有 provider 选择、真实临时 SQLite/LanceDB factory、权限 corpus、warmup/close 和 clarity/持久日志前后快照。
3. `infer()` 阻塞等待响应队列时，`close()` 只终止进程，没有唤醒等待线程；close 自身有界，但调用方仍等满 16 秒 timeout。

### 6.2 修复

1. worker 在导入 torch 后、加载 tokenizer/模型前检查 `torch.cuda.is_available()`；CUDA 不可用固定发 `specialist_load_failed` fatal，不再发 READY。
2. close 进入 `closing` 后向内部响应队列写入关闭 sentinel；在途 infer 立即返回 `specialist_unavailable`，随后仍按 shutdown / terminate / kill 顺序有界收口。
3. evaluator 新增必填 `--provider r3_v2|general_llm|local`，由 factory 按 provider 构建正式 runtime；负责 warmup、probe、close、端到端墙钟和 SQLite clarity/检索日志前后快照。
4. 新增 `backend.tests.route_runtime_isolated_factory:create_engine`：每次只在 OS 临时目录创建真实 SQLite/LanceDB；写入脱敏固定起点、两条允许证据，以及另一个 NPC 表中的禁止私有节点。`general_llm` 使用不访问外部 API 的确定性测试 client，`r3_v2` 仍使用批准的真实 worker。
5. 新增 `backend/tests/fixtures/route_runtime_corpus.jsonl`：两个脱敏 case 均声明 expected 与 forbidden IDs；不连接或复制正式存档。
6. 修复 evaluator 按脚本路径运行时缺少项目根 `sys.path` 的 CLI 入口问题，并增加 `--help` 回归。

### 6.3 实现期证据

1. 三个失败反馈环先稳定复现，再修复为 3 passed：CUDA 早拒绝、close 唤醒、evaluator provider/副作用契约。
2. 合并聚焦门禁：66 passed；真实 SQLite/LanceDB local 自测为 2/2 expected、0 forbidden、目标 provider 2/2、side-effect-free。
3. CUDA-disabled 真实 smoke 使用 `CUDA_VISIBLE_DEVICES=-1`：2034.256 ms 返回 `specialist_load_failed`，健康状态未进入 ready。Windows 下空字符串等同未设置，不能作为禁用证据。
4. 真实推理中关闭：close 1510.58 ms，在途线程已退出，返回 `specialist_unavailable`，worker 状态为 `closed`。
5. 三 provider 真实隔离报告均为 2 个 case、expected hit rate 1.0、forbidden 0、目标 provider 采用 2/2、side-effect-free：
   - `general_llm`：`F:/AIScLocalArtifacts/memory-route/artifacts/route-runtime-implementation-general-20260721.json`，SHA-256 `747694ea930b2cf427eddfb271502c38e74dc0202bd39ef8b38e7beb3c20d338`。
   - `local`：`F:/AIScLocalArtifacts/memory-route/artifacts/route-runtime-implementation-local-20260721.json`，SHA-256 `fc9d14f6c487027787e47b9f2c62022b20375eb5b4f4cf594db0daa422d5775b`。
   - `r3_v2`：`F:/AIScLocalArtifacts/memory-route/artifacts/route-runtime-implementation-r3-v2-20260721.json`，SHA-256 `1faaac305613f3a1b1e625e8dcf178bfe89fc0c7153620761617879400f8372b`；warmup 成功，端到端两 case 37112.041 ms。
6. 完整后端回归：146 passed、3 subtests passed、3 failed。失败仍是未修改的 `test_schedule_candidates.py` 夹具缺少既有 `task_runtime_metadata()`，与本次 Memory 修复无关。

本次只得出“修复实现完成，待独立复测”。测试会话应在原 test record 追加有界复测；在该记录通过前，整体仍不得宣称完成。
