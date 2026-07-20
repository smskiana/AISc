> 执行案：[2026-07-20_记忆路由专项模型部署与训练_plan.md](2026-07-20_记忆路由专项模型部署与训练_plan.md)
>
> 测试记录：[2026-07-20_记忆路由专项模型部署与训练_test.md](2026-07-20_记忆路由专项模型部署与训练_test.md)

# 记忆路由专项模型部署与训练 - 执行记录

## 1. 状态

实现完成，待独立测试。

已完成训练环境、底模冻结、BF16/NF4 推理、单步 LoRA 反向传播、极小集过拟合、Adapter 重载、96 条人工批准 corpus 的正式 Route LoRA SFT、字段级离线评估与聚焦契约测试。本轮没有接入正式 provider，也没有修改运行配置或连接正式存档。

本记录不声明专项模型达到替换资格。当前没有只连接隔离真实 SQLite/LanceDB 副本且注入 `llm_full_route` 的 engine factory，因此检索级 R0/R1/R2/R3 对照仍属于独立测试未覆盖项，不能用本次字段级结果替代。

## 2. 模型指导与事实复核

1. 使用附件 API Key 查询服务端模型，并选择可用最高档通用模型 `qwen3.7-max` 做执行前审阅；凭据未写入仓库、命令记录或本文。
2. 采纳其“独立 Python 3.11、先 BF16 后 NF4、项目外产物、极小集过拟合、隔离检索副作用”的保守建议。
3. 拒绝其过期版本矩阵和“Qwen3-0.6B 可能未发布”的判断。官方仓库已确认存在，实际 revision 为 `c1899de289a04d12100db370d81485cdf75e47ca`，模型配置标注 Transformers 4.51+，许可证为 Apache-2.0。

## 3. 实际改动

1. 新增 `backend/training/memory_route/`：schema v1、正式枚举白名单、UTF-8 JSONL、分组切分、审核门禁、采集、NF4/BF16 LoRA 训练和确定性评估。
2. 采集器可通过正式 `LlmDirectionProvider` 取教师原始方向，再通过 `DirectionResolver` 验证/校准；可选 engine factory 时只调用 `RetrievalEngine.probe()`，禁止 clarity 恢复与持久检索日志。
3. 训练只计算 assistant JSON 的 loss，关闭 thinking，显式追加 EOS；默认拒绝未批准样本，`--allow-unreviewed-smoke` 产物带 `review_bypass: true`。
4. 评估记录 schema 合法率、实体召回、字段准确率、未知实体、检索命中、p50/p95/p99、峰值显存与逐样本输出。
5. 新增 6 条脱敏 smoke 候选夹具，仅用于工具闭环，不作为人工 golden corpus。
6. 更新 `.gitignore`、后端训练索引、Memory 执行证据索引和 codebase-memory 更新时间；正式 provider、运行配置、数据库、Unity/C# 均未修改。

## 4. 环境与产物

- Python：3.11.9，独立 venv `C:/Users/HP/.cache/AISc/memory-route/venv`。用户要求后续不继续向 C 盘堆量后，模型与所有新增实验产物改到 F 盘。
- PyTorch：2.11.0+cu128；Transformers：5.14.1；PEFT：0.19.1；datasets：4.8.4；accelerate：1.13.0；bitsandbytes：0.49.2。
- GPU：NVIDIA GeForce RTX 4060 Laptop GPU，8188 MiB；CUDA runtime 12.8；BF16 可用。
- 项目外根目录：`F:/AIScLocalArtifacts/memory-route/`。
- 模型缓存约 1448.8 MB，实验产物约 148.4 MB；仓库没有模型权重、Adapter、真实数据或 API Key。

## 5. 实现期最低门禁

1. CUDA/BF16 运算：通过。
2. Qwen3-0.6B BF16 确定性非 thinking 生成：通过，峰值约 1582.5 MB。
3. Windows 原生 bitsandbytes NF4 加载与生成：通过，峰值约 959.1 MB。
4. 单步 NF4 LoRA：通过；train loss 4.615，validation loss 3.137，Adapter 与 manifest 保存成功，峰值约 1605.0 MB。
5. 极小集过拟合：通过；3 条 train 样本 60 步，最终单步 loss 已降至约 0.00016，整体 train loss 0.2785，峰值约 1690.3 MB。
6. Adapter 重载与 train split 推理：通过；3/3 schema 合法、明确实体召回 1.0、字段准确率 1.0、未知实体 0。
7. zero-shot 与 one-step 未见 test 样本：schema 合法率均为 0，按 smoke 口径如实保留，未当作质量通过。
8. `pytest backend/tests/test_memory_route_training_contract.py -q`：5 passed，覆盖 schema/UTF-8、审核与泄漏门禁、分组切分、正式枚举同步和 resolver 校准。

## 6. 独立测试未覆盖项

1. 96 条合成 teacher corpus 已获人工批准并完成正式 SFT；原 `smoke_pending.jsonl` 仍只承担 smoke，不纳入正式训练。
2. 尚未提供经批准的隔离真实会话、期望节点、权限复核结果和只连接隔离图副本的 engine factory，无法在同一 `llm_full_route` 条件下完成 R0/R1/R2/R3 检索级公平比较。
3. 当前 test split 只有 12 条合成样本，字段准确率暴露的弱项需要独立测试会话判定是否达到继续调参或接入候选线。
4. 因此本执行会话只得出“实现完成，待独立测试”，不作替换资格判断。

## 7. 后续入口

1. 新开独立测试会话，读取 TestingAndDiagnostics、plan 与本 execution，创建对应 test record，并复核字段级报告和质量弱项。
2. 如需完成检索级验收，先提供隔离 SQLite/LanceDB 副本的 engine factory，并为目标 mode 注入 `llm_full_route`；不得连接正式存档。
3. 独立测试未通过时回到新的执行会话修复或调参；不得在测试会话顺手修改实现。
4. 正式 provider 接入、shadow 和运行配置修改仍需另行方案或更新原 plan，本记录不授权执行。

## 8. codebase-memory 同步

1. canonical `AISc` moderate 返回 `indexed`，但仍保持 11362 nodes / 25928 edges，且搜索不到新增训练符号；响应的 expected 值高于实际值，因此未把它误记为新鲜覆盖。
2. 新建并持久化 `AISc_memory_route_training_20260720` moderate 索引：6510 nodes / 21010 edges，与 expected 完全一致。
3. 已通过 `search_graph` 验证 `RouteDataset`、`collect_records`、`train`、`evaluate` 和 `validate_records` 均可检索。

## 9. 教师数据生成脚本补充

1. 离线采集器现可显式构建 OpenAI-compatible 教师客户端，模型名或部署 ID 与 base URL 通过 CLI 提供，密钥只从指定环境变量读取。
2. 新增 `--max-samples` 调用上限，便于先做单样本兼容和费用 smoke；输出继续保持 `pending`，不会绕过人工 golden corpus 审核。
3. 聚焦测试新增显式教师注入、调用次数上限和正式 resolver 校准覆盖。本补充只完善数据生成入口，未调用外部服务、未上传项目数据，也未改变“实现未完成”的总体状态。
4. `pytest backend/tests/test_memory_route_training_contract.py -q`：6 passed；训练 venv 对采集脚本执行 `py_compile` 通过，CLI `--help` 加载通过，凭据/私有端点扫描无命中。
5. 补充后再次刷新 `AISc_memory_route_training_20260720` moderate 索引；服务返回 6510 nodes / 21010 edges，而 expected 为 6516 / 21073，已在索引状态文档保留未完全刷新的事实。
6. 首次在独立训练 venv 运行教师采集器时发现 `openai` 未进入训练锁，导致模块导入阶段失败；现已把 `openai==2.43.0` 纳入锁文件并增加直接依赖回归断言。该错误属于环境声明遗漏，不涉及数据或外部服务响应。
7. 教师请求随后被正式 provider 统一收口为 `llm_invalid`，无法区分 HTTP 异常与非 JSON 响应；离线采集器现以包装器保留截断诊断，并替换实际 API Key 后再进入本地异常。正式运行时 provider 的稳定失败口径未改动。
8. 全量 smoke 中教师把 `time_scope` 返回为数组，暴露正式方向校验器对错误 JSON 形状直接执行集合成员判断的问题。现统一收口标量枚举、枚举数组和 mention 文本数组的错误形状，非法值降级并进入 `validation_errors`，不再中断整批采集。
9. 首批 6 条教师输出暴露两项质量缺陷：未知地点只因出现在 query 中被误绑到首个人物；运行时方向 Prompt 只写“系统白名单”但未列出完整枚举。现修正 mention 精确绑定，并仅在离线采集入口叠加训练 schema 完整白名单；正式运行 Prompt 与 DTO 未改变。
10. 新增确定性脱敏合成候选生成器，默认输出 96 条、12 类场景和覆盖摘要；候选明确标记不含真实会话数据，并按主题生成多个 `source_group`。本步骤只生成待抽检 candidate，不调用教师、不自动批准，也不把本地产物提交 Git。
11. 用户完成 96 条合成候选抽检并明确授权上传后，采集器新增逐条 checkpoint 与 `--resume`。中途失败时按 `sample_id` 跳过已完成记录；候选文件与续跑输出不匹配时拒绝继续。最终完成后仍统一重算分组 split，所有记录保持 `pending`。

## 10. 人工批准 corpus 与正式 SFT

1. 用户于本执行会话明确确认已人工复核并批准 `F:/AIScLocalArtifacts/memory-route/datasets/synthetic_teacher_pending.jsonl` 的全部 96 条记录。
2. 审批前验证通过：96 条、48 个 `source_group`、无重复 `sample_id`，train / validation / test 分别为 76 / 8 / 12，schema、正式枚举白名单、分组无交叉和稳定 ID 泄漏门禁均通过。
3. pending 原件保留不变；审批前后 SHA-256 均为 `d0a2192e5d18efcbcc0692632e827379da18a4e7756c724b4a99bc249f546a8e`。
4. 新生成 `F:/AIScLocalArtifacts/memory-route/datasets/synthetic_teacher_approved.jsonl`，96 条 `review.status` 均为 `approved`，`review.reviewer` 为 `user_confirmed_manual_review`，`review.reviewed_at` 为 `2026-07-20T16:12:26+08:00`；approved corpus SHA-256 为 `cfdf709c613d5f867aca6093338ccbdc75812eb57172c6e7dccc19f35b6cb2b4`。
5. 正式 SFT 使用冻结 revision `c1899de289a04d12100db370d81485cdf75e47ca`、NF4、seed 20260720、max length 768、micro batch 1、gradient accumulation 8、learning rate 2e-4、3 epochs、LoRA rank / alpha / dropout 为 16 / 32 / 0.05；未使用 `--allow-unreviewed-smoke`。
6. 训练完成 30 steps，总 train loss 0.2629，最终 validation loss 0.2103，耗时 202.194 秒，峰值显存 2112.5 MB；manifest 明确记录 `review_bypass: false`。
7. 最终 Adapter、epoch checkpoints、manifest 与日志保存在 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-sft-approved-96/` 和相邻 `logs/`，未进入 Git。

## 11. 字段级离线评估

1. 使用最终 Adapter 对保留的 12 条 test split 做确定性生成，并继续经过正式 `DirectionResolver` 校准；未传入 engine factory，未连接正式或隔离图，也未产生检索副作用。
2. 结构化报告位于 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-sft-approved-96-test-eval.json`：schema 合法率 1.0、明确实体召回率 1.0、聚合字段准确率 0.7083、未知实体数 0。
3. 逐字段报告位于 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-sft-approved-96-test-field-metrics.json`。准确率分别为：`entity_mentions` 1.0、`location_mentions` 0.4167、`themes` 0.9167、`relation_facets` 0.75、`time_scope` 1.0、`source_preferences` 0.5833、`recall_intent` 1.0、`negative_directions` 0.75、`retrieval_query` 0.25、`query_constraints` 0.4167。
4. 延迟为 p50 10822.319 ms、p95 / p99 16534.186 ms，峰值显存 959.1 MB。该结果显示结构和核心实体稳定，但地点、检索 query 与约束字段仍明显不足，只能作为后续独立验收和是否继续调参的证据。
5. 报告中的 `retrieval_hit_rate=0` 源于 12 条合成记录没有 `expected_node_ids` 且本轮未提供 engine factory，不能解释为检索失败或检索通过。
6. 实现期最低门禁：训练 venv 对 `common.py`、`train_route_lora.py`、`evaluate_route_specialist.py` 执行 `py_compile` 通过；项目测试环境执行 `pytest backend/tests/test_memory_route_training_contract.py -q` 为 11 passed。
7. codebase-memory canonical `AISc` 在本轮开始时为 11434 nodes / 26493 edges，actual 与 expected 一致；本轮只新增项目外 corpus / Adapter / 报告并更新本执行记录，没有代码符号变化，因此无需重复重建代码图。
8. 未新增 `specialist_python` provider，未修改 `memory_retrieval.yaml`、数据库、Unity/C#、场景、Prefab 或正式存档。

## 12. 第二批 384 条脱敏合成候选

1. 在不修改 `synthetic_teacher_approved.jsonl` 及其 96 条已批准数据的前提下，扩展 `generate_synthetic_candidates.py`：场景由 12 类增至 24 类，并增加 `--batch-prefix`、`--start-index`、可重复的 `--existing-dataset`、规范化输入冲突门禁和分层抽检输出。
2. 规范化输入比较对完整 input DTO 执行 Unicode NFKC、连续空白折叠和 JSON 键稳定排序；数组顺序保持不变，避免抹掉近期对白的时序语义。生成器在写文件前拒绝批内重复、新旧规范化输入重复、`sample_id` 冲突和 `source_group` 冲突。
3. 使用 `count=384`、`seed=20260720`、`batch_prefix=synthetic-b02`、`start_index=97`，并以原 96 条 approved corpus 为冲突基线。结果为 384 条、24 类、每类 16 条、192 个 `source_group`；批内规范化输入重复、新旧规范化输入重复、`sample_id` 冲突和 `source_group` 冲突均为 0。
4. 候选位于 `F:/AIScLocalArtifacts/memory-route/datasets/synthetic_b02_candidates.jsonl`，SHA-256 为 `c5819130e4f701e64968c08edc42d5e753eeb91bafce247fd5be7def6a8ada1a`。
5. 覆盖摘要位于 `F:/AIScLocalArtifacts/memory-route/datasets/synthetic_b02_candidates.summary.json`，SHA-256 为 `3c6f5b2b96e6ba6839207c7a5a0140cbc7a4e07c8610138cb4359eeac70118ed`；分层抽检位于 `F:/AIScLocalArtifacts/memory-route/datasets/synthetic_b02_candidates.stratified_sample.jsonl`，按 24 类各抽 1 条，SHA-256 为 `0d6641918e5514619b6a847a680d062272c032886025f76beb19243dfa7e08d2`。
6. 本步骤只生成 `candidate`，未设置或读取教师凭据，未调用教师 API，未生成教师标签，未批准数据，也未启动训练或修改原 96 条 corpus。
7. 最低门禁：训练 venv 对生成器执行 `py_compile` 通过；项目 pytest 环境执行 `backend/tests/test_memory_route_training_contract.py -q` 为 12 passed；`git diff --check` 通过。该门禁不替代后续人工抽检或独立测试。
8. 当前会话未暴露 codebase-memory MCP 图工具，因此无法按规则刷新或验证代码图，也未改写 `docs/AIChanges/codebase-memory-mcp_更新.md` 的既有状态；本次仅以功能索引和精确 `rg` 完成受限代码发现，后续具备 MCP 工具的会话需补做索引刷新与符号验证。

## 13. 第二批教师标签采集

1. 用户完成 24 类分层抽检并明确批准将全部 384 条脱敏候选发送到教师 API；使用既有 OpenAI-compatible 入口和 `qwen3.7-max`，先完成 1 条费用/兼容 smoke，再以 `--resume` 顺序处理剩余 383 条。
2. API Key 只注入采集子进程环境，进程退出时删除；未写入仓库、数据产物或本文。由于密钥曾由用户直接发送到对话，仍建议在本批次完成后轮换。
3. 采集进程正常退出，总耗时约 7820 秒。输出位于 `F:/AIScLocalArtifacts/memory-route/datasets/synthetic_b02_teacher_pending.jsonl`，SHA-256 为 `2a1aa5a7595176efa7251e6006a79be99f808cf11612ac7355a455dcba225198`。
4. 收口校验通过：候选 384 条、pending 384 条、重复 `sample_id` 0、缺失候选 ID 0、额外输出 ID 0；全部 `review.status=pending`。192 个 `source_group` 均只进入一个 split，train / validation / test 为 306 / 38 / 40。
5. 使用正式 schema 和枚举门禁执行 `validate_records(require_approved=False)` 通过；抽查输入、教师原始方向、校准方向和校准证据的 Unicode 码点正常。PowerShell 默认控制台曾错误渲染中文，但 JSONL 内容未损坏。
6. 原 96 条 `synthetic_teacher_approved.jsonl` 保持不变，SHA-256 仍为 `cfdf709c613d5f867aca6093338ccbdc75812eb57172c6e7dccc19f35b6cb2b4`。本步骤没有批准第二批数据，也没有启动训练或覆盖既有 Adapter。

## 14. 第二批人工批准 corpus

1. 用户明确确认第二批 384 条教师标签人工审核通过。保留 `synthetic_b02_teacher_pending.jsonl` 原件不变，另生成 `F:/AIScLocalArtifacts/memory-route/datasets/synthetic_b02_teacher_approved.jsonl`。
2. 384 条 `review.status` 均为 `approved`，`review.reviewer` 均为 `user_confirmed_manual_review`，`review.reviewed_at` 均为 `2026-07-20T18:59:34+08:00`。
3. approved corpus 使用正式 schema、枚举、稳定 ID 泄漏、分组无交叉和 `require_approved=True` 门禁验证通过；逐条移除 `review` 后与 pending 原件比较，非审核字段差异数为 0。
4. 第二批 approved corpus SHA-256 为 `3cddfe4de07327de73808e8fc84d38cba289637432976b921253b87217a3bc18`；第二批 pending 原件 SHA-256 仍为 `2a1aa5a7595176efa7251e6006a79be99f808cf11612ac7355a455dcba225198`；原 96 条 approved corpus SHA-256 仍为 `cfdf709c613d5f867aca6093338ccbdc75812eb57172c6e7dccc19f35b6cb2b4`。
5. 本步骤只固化人工批准结果，没有合并或覆盖旧 96 条 corpus，没有启动训练、评估或修改既有 Adapter。

## 15. R3 v2 第二轮离线训练与冻结 test 对比

1. 本轮继续以原 plan 为唯一方案来源，只执行离线训练和实现期最低门禁；未接正式 provider、检索 engine、数据库、运行配置或正式存档，也未创建第二份 plan 或 test record。
2. R3 v1 失败分析沿用第 11 节：12 条冻结 test 上 schema 合法率与明确实体召回率均为 1.0，但聚合字段准确率仅 0.7083，主要弱项为 `location_mentions=0.4167`、`retrieval_query=0.25`、`query_constraints=0.4167` 和 `source_preferences=0.5833`。
3. canonical `AISc` 已在训练前以 moderate + persistence 刷新，actual / expected 均为 11439 nodes / 26549 edges；图中已验证 `validate_records` 等训练符号可检索，并同步更新 `docs/AIChanges/codebase-memory-mcp_更新.md`。
4. 新建项目外组合 corpus `F:/AIScLocalArtifacts/memory-route/datasets/route_r3_v2_approved_480.jsonl`，SHA-256 为 `0f79f9dc5c1dc56fd4254b8f64a93e149a0f3aa113ad9555651cba645c0bf905`。它原样组合旧 96 条与第二批 384 条 approved 数据，共 480 条，train / validation / test 为 382 / 46 / 52，全部 `review.status=approved`。
5. 正式 schema、枚举、稳定 ID 泄漏和 `require_approved=True` 门禁通过；旧批 48 个与第二批 192 个 `source_group` 交叉为 0，`sample_id` 交叉为 0。旧 96 条中的 12 条 test 保持原 split，未进入训练；其稳定 JSON canonical SHA-256 为 `259b27598e802521f39ebc5ab445538069e6cab555211b1e9b000c5018e5ab4c`。
6. R3 v2 使用与 v1 相同的冻结底模 revision、NF4、seed 20260720、max length 768、micro batch 1、gradient accumulation 8、learning rate 2e-4、3 epochs 和 LoRA 16 / 32 / 0.05；未使用审核绕过。新产物目录为 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-r3-v2-approved-480/`，保留 checkpoint-48 / 96 / 144、最终 Adapter 和 manifest。
7. 训练完成 144 steps，总 train loss 0.1603，最终 validation loss 0.1062，耗时约 840.8 秒，峰值显存 2132.0 MB，manifest 记录 `review_bypass: false`。R3 v2 Adapter SHA-256 为 `cd2676f7f64f28a351fb35b2d2d76fa01b30662a509bf7bbdcced6f9cf92b8d`。
8. R3 v1 Adapter 在训练前后 SHA-256 均为 `6b420cf869b8c666e79455156fda59a6a62b357db7da86051a5f0d07b0902f1e`，旧 Adapter、checkpoint 和首轮报告均未覆盖。v1 重跑报告为 `route-lora-r3-v1-frozen-test-rerun.json`，v2 报告为 `route-lora-r3-v2-frozen-test.json`。
9. 相同冻结 test 上，v1 / v2 的 schema 合法率均为 1.0、明确实体召回率均为 1.0、未知实体均为 0；聚合字段准确率由 0.7083 提升到 0.8083。p50 由 11138.018 ms 降至 10847.326 ms，p95 / p99 由 12466.220 ms 降至 11671.412 ms；峰值显存均为 959.1 MB。
10. v2 字段准确率为：`entity_mentions=1.0`、`location_mentions=0.75`、`themes=0.6667`、`relation_facets=0.8333`、`time_scope=1.0`、`source_preferences=0.8333`、`recall_intent=0.9167`、`negative_directions=0.8333`、`retrieval_query=0.4167`、`query_constraints=0.8333`。相比 v1，地点、query、约束和来源偏好改善，但 `themes` 下降 0.25、`recall_intent` 下降 0.0833，且 2 条样本总字段命中回退。
11. 统一对比报告为 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-r3-v1-v2-frozen-test-comparison.json`，SHA-256 为 `521213cb8d610f28f66ffa2ca96dc1f3b147430fa1c8818bdf96c30ffc047ccc`。报告中的 `retrieval_hit_rate=0` 仍因冻结合成 test 没有 `expected_node_ids` 且未提供 engine factory，不能解释为检索通过或失败。
12. 本轮结论仅为“R3 v2 离线训练和实现期最低门禁完成，待独立测试”。v2 改善主要弱字段但存在局部回退，是否达到后续候选资格必须在新的独立测试任务中判定；本执行会话到最低门禁后停止。
13. 实现期最低门禁：训练 venv 对 `common.py`、`train_route_lora.py`、`evaluate_route_specialist.py` 执行 `py_compile` 通过；设置仓库根 `PYTHONPATH` 后执行 `pytest backend/tests/test_memory_route_training_contract.py -q` 为 12 passed；`git diff --check` 通过。首次直接调用全局 pytest 因环境未包含仓库根而在收集期报 `ModuleNotFoundError: backend`，补齐项目启动环境后通过，未涉及代码修复或测试重试掩盖。

## 16. R3 v3 本地脱敏纠错候选

1. 本轮继续以原 plan、execution 和未完整通过的独立 test 为唯一上下文，只针对 R3 v2 暴露的地点、多人物、错误前提及检索 query / 噪声风险生成本地纠错候选；未修改训练代码、正式 provider、运行配置、数据库、Unity 资产或既有 approved corpus。
2. 候选由 4 个独立进程并行生成，每个 shard 40 条，共 160 条：`location` 覆盖 `locate_current`、`locate_last_destination`、`location_history`、`scene_location_noise`、`time_comparison` 各 8 条；`multi-person` 覆盖 `multi_person_competition`、`negation_correction`、`participant_scope`、`relationship_compare`、`speaker_attribution` 各 8 条；`false-premise` 覆盖 `false_premise`、`no_relevant_memory`、`private_knowledge`、`uncertain_rumor` 各 10 条；`query/noise` 覆盖 `alias_resolution`、`cross_turn_reference`、`irrelevant_context_noise`、`no_relevant_memory` 各 10 条。
3. 四份候选分别位于 `F:/AIScLocalArtifacts/memory-route/datasets/route_r3_v3_location_candidates.jsonl`、`r3_v3_correction_multi_person_candidates.jsonl`、`r3_v3_false_premise_candidates.jsonl` 和 `r3_v3_candidates_query_noise.jsonl`；SHA-256 依次为 `b5600a87cab672f20b1b40abf551c3e8eed6d1fd6f37eb5a47114b6f890ddb6a`、`150869385ea60302158268d854e9a25631e9daae8b280248178d32d91dd9f100`、`07a625136c462bd4bd0c883d3d2d4d5b0e8242d4dcc1fb464ba9fdf7caa83a32`、`70a356fe0a086dfc8ebef29cf4ebe0054f19830f6cdbc9b14ae8e5a7edc25e26`。
4. 每个候选文件均生成对应 `.summary.json` 和 `.stratified_sample.jsonl`；分层抽检共 18 条，覆盖全部 18 个 shard 内类别。逐条检查 query、近期对白 / 记忆与 `review_focus` 后，人物归属、地点时态、否定纠正、错误前提、隐私、传闻、代词与无关噪声口径一致。
5. 联合 160 条对既有 `synthetic_teacher_approved.jsonl` 与 `synthetic_b02_teacher_approved.jsonl` 共 480 条 approved 基线执行统一门禁：批内 `sample_id` 重复、批内规范化 input 重复、既有 `sample_id` 冲突、既有 `source_group` 冲突和既有规范化 input 冲突均为 0；该检查同时覆盖四个 shard 彼此之间的冲突。
6. 160 条均为 `synthetic=true`、`contains_real_session_data=false`，只含空占位 `raw_direction`；不存在教师原始标签、`expected_direction` 或审核记录。全程未读取或设置教师凭据、未调用教师 API、未批准数据、未合并 golden corpus、未启动训练或评估。
7. 最低门禁：训练 venv 对 `generate_synthetic_candidates.py` 与 `common.py` 执行 `py_compile` 通过；设置仓库根 `PYTHONPATH` 后执行 `pytest backend/tests/test_memory_route_training_contract.py -q` 为 `12 passed in 1.24s`；`git diff --check` 通过，仅报告工作区既有文件的 LF/CRLF 提示。
8. canonical codebase-memory `AISc` 在本轮开始时为 11439 nodes / 26549 edges，训练生成入口可检索且与 `docs/AIChanges/codebase-memory-mcp_更新.md` 记录一致。本轮没有代码符号变化，只更新本 execution，因此不重复重建代码图。本步骤结论仅为“R3 v3 本地候选生成与实现期最低门禁完成，待后续人工抽检决定是否进入教师标注”；不构成数据批准、训练授权或专项模型验收通过。

## 17. R3 v3 目标方向填写与待抽检集

1. 用户确认候选分层抽检通过后，要求由智能体直接阅读输入并填写目标 `RetrievalDirection`，而不是调用 R3 v2 Adapter 自举标注。首次误解曾启动本地评估器；在模型只完成加载且尚未写出报告时已终止，临时推理输入已删除，没有模型输出进入本批标签。
2. `location` 与 `multi-person` 两个 shard 由独立子智能体逐条填写；`false-premise` 与 `query/noise` 由主智能体按相同 schema 和正式枚举补齐，并通过 `review.reviewer` 与 `evidence.label_source` 如实区分来源。全部 160 条保持 `review.status=pending`，不因智能体填写自动视为人工批准。
3. 四份待抽检文件分别为 `F:/AIScLocalArtifacts/memory-route/datasets/route_r3_v3_location_labeled_pending.jsonl`、`r3_v3_multi_person_labeled_pending.jsonl`、`r3_v3_false_premise_labeled_pending.jsonl` 和 `r3_v3_query_noise_labeled_pending.jsonl`；SHA-256 依次为 `8c63815f7591b35da92db722b88317632eb09adf7f42efbd4ede7c88bec77d47`、`0eef303792c52a79b7d6cda806255026d9b31dcc849a8fa4521726707a598b33`、`897f649d35187c438889150e3f444e9503b64ca1ae949e77f6a52f76af39a8b6`、`f7f9619de6f0e9aedbf342c45f2464715794d0b84b891baefc8438df29b5fadb`。
4. 每条记录均满足 `raw_direction == calibrated_direction == label`，使用正式 10 字段方向 schema，未包含 `node_id`、`node_ids`、`edge_id` 或 `edge_ids`。按 `source_group` 确定性切分后，联合 train / validation / test 为 126 / 16 / 18，四个 shard 之间没有 `sample_id` 重复或 group 跨 split。
5. 统一分层抽检文件为 `F:/AIScLocalArtifacts/memory-route/datasets/r3_v3_labeled_pending.stratified_sample.jsonl`，共 18 条，覆盖四个 shard 的全部类别；各 shard 同时保留自己的 `.summary.json` 与 `.stratified_sample.jsonl`。
6. 正式 `dataset_schema.json` 与 `validate_records(require_approved=False)` 对各 shard 及联合 160 条均通过；聚焦契约测试为 `12 passed in 1.28s`，`git diff --check` 通过且仅有工作区既有 LF/CRLF 提示。
7. 本步骤未调用教师 API、未使用本地专项模型生成标签、未连接检索 engine、未批准数据、未合并 golden corpus、未训练或覆盖 Adapter。当前结论仅为“目标方向填写完成，待用户抽检”；只有用户复核后另行明确批准，才能生成 approved corpus 或进入训练。

## 18. R3 v3 人工批准 corpus

1. 用户确认 18 条分层目标方向抽检通过，并明确批准全部 160 条为训练数据。四份 pending 原件保持不变，另生成 `F:/AIScLocalArtifacts/memory-route/datasets/route_r3_v3_approved_160.jsonl` 与对应 `.summary.json`。
2. 160 条记录的 `review.status` 均为 `approved`，`review.reviewer` 均为 `user_confirmed_manual_review`，`review.reviewed_at` 均为 `2026-07-20T20:43:37+08:00`；除 `review` 外，pending 与 approved 的字段差异数为 0。
3. approved corpus 包含 87 个 `source_group`，train / validation / test 为 126 / 16 / 18；正式 schema、枚举、稳定 ID 泄漏、分组无交叉和 `validate_records(require_approved=True)` 门禁通过。
4. 四份 pending 源文件 SHA-256 依次保持为：location `8c63815f7591b35da92db722b88317632eb09adf7f42efbd4ede7c88bec77d47`、multi-person `0eef303792c52a79b7d6cda806255026d9b31dcc849a8fa4521726707a598b33`、false-premise `897f649d35187c438889150e3f444e9503b64ca1ae949e77f6a52f76af39a8b6`、query/noise `f7f9619de6f0e9aedbf342c45f2464715794d0b84b891baefc8438df29b5fadb`。
5. R3 v3 approved corpus SHA-256 为 `1d0b3dbc2c4d077684bceddf569f12c8c2f7346c2a6ade8b0d47c0b73ef69452`。聚焦契约测试为 `12 passed in 1.18s`，`git diff --check` 通过且仅有工作区既有 LF/CRLF 提示。
6. 本步骤只固化用户人工批准结果，没有修改旧 96 / 384 / 480 条 corpus，没有调用教师 API、合并训练集、启动训练、评估或覆盖任何 Adapter。后续训练必须由新的明确指令授权。

## 19. R3 v3 离线训练与同一冻结 test 对比

1. 本轮继续以原 plan 为唯一方案来源，只执行已批准 corpus 的离线训练、字段级评估和实现期最低门禁；未接正式 provider、检索 engine、数据库、运行配置或 Unity 资产，也未创建第二份 plan 或新 test record。
2. 训练前以 `moderate + persistence` 刷新 canonical `AISc` codebase-memory，结果为 11439 nodes / 26549 edges；图中已验证 `validate_records`、`build_training_text`、`collect_records` 和合成候选生成入口可检索，并同步更新 `docs/AIChanges/codebase-memory-mcp_更新.md`。
3. 新建项目外组合 corpus `F:/AIScLocalArtifacts/memory-route/datasets/route_r3_v3_approved_640.jsonl`，SHA-256 为 `42e427f97573fd3847f3f4d87a7d6911b3fb60848ecf6570bc89f8c210d63c1a`。它原样组合 R3 v2 的 480 条与新批准的 160 条，共 640 条、327 个 `source_group`，train / validation / test 为 508 / 62 / 70，全部 `review.status=approved`。
4. 两批 corpus 的 `sample_id` 和 `source_group` 交叉均为 0；正式 schema、枚举、稳定 ID 泄漏、分组无交叉和 `require_approved=True` 门禁通过。原 96 条 corpus 中的 12 条冻结 test 在组合 corpus 中逐对象一致且仍全部保持 `split=test`，未进入训练或验证。
5. R3 v3 沿用 v1/v2 的冻结底模 revision、NF4、seed 20260720、max length 768、micro batch 1、gradient accumulation 8、learning rate 2e-4、3 epochs 和 LoRA 16 / 32 / 0.05，未使用审核绕过。新产物目录为 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-r3-v3-approved-640/`，保留 checkpoint-64 / 128 / 192、最终 Adapter 和 manifest。
6. 训练完成 192 steps，总 train loss 0.1504，最终 validation loss 0.09641，耗时 1779.98 秒，峰值显存 2131.3 MB；manifest 记录 `review_bypass: false`。R3 v3 Adapter SHA-256 为 `2fda5b0f3061dae1e591b92fc03063ea09fd0089ad0e7239bedb7a116b62961b`。
7. R3 v1 / v2 Adapter 训练前后 SHA-256 仍分别为 `6b420cf869b8c666e79455156fda59a6a62b357db7da86051a5f0d07b0902f1e` 和 `cd2676f7f64f28a351fb35b2d2d76fa01b30662a509bf7bbdcced6f9cf92b8d`；旧 Adapter、checkpoint 和报告未被覆盖。
8. R3 v3 在原 12 条冻结 test 上的报告为 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-r3-v3-frozen12.json`，SHA-256 为 `b2e74e86d6b636d1d5bf3e5e68a0afc90fd80070cf946d088a5c2c8d049f60ee`。schema 合法率 1.0、明确实体召回率 1.0、聚合字段准确率 0.8083、未知实体 0，与 R3 v2 的总体质量指标持平。
9. R3 v3 逐字段准确率为：`entity_mentions=1.0`、`location_mentions=0.75`、`themes=0.75`、`relation_facets=0.8333`、`time_scope=1.0`、`source_preferences=0.8333`、`recall_intent=1.0`、`negative_directions=0.75`、`retrieval_query=0.25`、`query_constraints=0.9167`。相比 v2，`themes`、`recall_intent` 和 `query_constraints` 各提升 0.0833，`negative_directions` 下降 0.0833，`retrieval_query` 下降 0.1667，净准确率无改善。
10. 三方统一报告为 `F:/AIScLocalArtifacts/memory-route/artifacts/longcat-vs-r3-v2-v3-frozen12-comparison.json`，SHA-256 为 `c8eb98a398f531be22d64820bed11c8adb2605f0d5f7197276aad194e8bb6452`。LongCat-2.0 API 基线复用独立测试任务对这 12 个完全相同 `sample_id` 已保存的原始响应和正式校准结果，未重复付费调用；其 schema 合法率 1.0、实体召回率 1.0、字段准确率 0.4917、未知实体 3。R3 v2/v3 字段准确率均高 0.3167，未知实体均少 3。
11. 本次 R3 v3 本地推理 p50 / p95 / p99 为 26318.450 / 29298.959 / 29298.959 ms，明显慢于 v2 已保存基线的 11115.177 / 12347.734 / 12347.734 ms；两次运行未交错且受本机状态影响，该差异需独立测试复核，本执行记录不将它解释为稳定性能回归。
12. 本轮未提供 engine factory 且冻结合成 test 没有 `expected_node_ids`，因此报告中 `retrieval_hit_rate=0` 仍表示“未评估”，不能解释为检索通过或失败。
13. 实现期结论仅为“R3 v3 离线训练和最低门禁完成，待独立测试”。v3 未在冻结字段准确率上超过 v2，且出现字段回退与本地延迟异常，不具备正式接入或替换资格；完成与改动风险匹配的最低门禁后停止，独立验收另开任务。
14. 实现期最低门禁：训练 venv 对 `common.py`、`train_route_lora.py`、`evaluate_route_specialist.py` 执行 `py_compile` 通过；正式 approved corpus 复验和冻结 12 条逐对象一致性检查通过；设置仓库根 `PYTHONPATH` 后使用项目可用的全局 pytest 执行 `backend/tests/test_memory_route_training_contract.py -q` 为 `12 passed in 1.24s`；`git diff --check` 通过，只输出工作区既有 LF/CRLF 提示。训练 venv 未安装 pytest，直接 `python -m pytest` 因 `No module named pytest` 未进入收集，因此按项目现有测试环境分工使用全局 pytest，未修改训练锁或用重试掩盖代码失败。
