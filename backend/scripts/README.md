# 后端脚本目录

## 文件夹功能

保存开发期跑测、诊断、数据维护和规范检查脚本。

## 文件夹内容

包括长跑测试、日志分析、数据库检查和项目约定检查。脚本产物应写入指定临时目录或 `docs/AIChanges/artifacts/`。

## 核心入口

- `check_project_conventions.py`：校验共享地点、行为、物品和 NPC 配置约定；不负责 Markdown 互链或测试记录完整性。
- `run_7day_benchmark.py`：需要多日运行、记忆/行为汇总或性能趋势时使用隔离长跑。
- `tune_memory_route_profiles.py`：需要基于真实记忆图与真实 LLM 调整性能、平衡、质量三档阈值时使用；注意真实调用成本和隔离数据。
- `evaluate_deep_retrieval.py`：需要快速比较三业务模式 × 三路由策略时使用离线固定图和 fake LLM，输出调用次数、路径、停止原因和向量查询次数。
- `evaluate_route_runtime.py`：使用显式标记为隔离的 `module:function` engine factory 和带允许/拒绝节点预期的 UTF-8 JSONL，只调用正式 `RetrievalEngine.probe()`，验证 provider chain、检索命中、权限、clarity/日志无副作用与调用计数。仓库内批准的脱敏入口为 `backend.tests.route_runtime_isolated_factory:create_engine` 和 `backend/tests/fixtures/route_runtime_corpus.jsonl`。

## 使用规则

1. 先确认普通聚焦测试不能回答问题，再选择专用脚本；不要把长跑脚本当作每次修改的默认门禁。
2. 执行前阅读目标脚本参数和数据写入范围，涉及存档、SQLite、LanceDB 或真实 LLM 时使用隔离副本。
3. 测试记录写明脚本、参数、数据源、墙钟、产物路径和结论；原始产物放入 `docs/AIChanges/artifacts/`。
4. `evaluate_route_runtime.py` 的 factory 函数必须设置 `aisc_isolated_retrieval_factory = True`，并接受 `r3_v2 / general_llm / local` provider ID；corpus 每条必须包含 `isolated_data: true`、`expected_node_ids` 和 `forbidden_node_ids`，否则脚本拒绝运行。
5. 三类 provider 必须分别传入 `--provider` 跑测。R3 运行时若为 worker 设置独立 `HF_HOME`，父进程 BGE cache 应通过 `SENTENCE_TRANSFORMERS_HOME` 指向已有本地 cache；同时设置 offline 环境变量，禁止测试意外访问 Hub。
