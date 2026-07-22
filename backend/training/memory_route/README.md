# 记忆路由专项模型离线工具

## 边界

本目录只负责 `Qwen/Qwen3-0.6B + Route LoRA` 的离线数据契约、采集、训练和评估。它不注册正式 provider，不修改 `memory_retrieval.yaml`，不启动 shadow，也不把模型、数据或 checkpoint 放入仓库。

方向字段、R3 v2 system prompt、紧凑 schema v1 messages 和方向序列化的权威位于 `backend/src/memory/route_specialist_contract.py`；本目录只通过 `common.py` 窄 re-export 复用，生产代码不得反向依赖训练目录。训练与运行时统一以 `enable_thinking=False` 构造 chat template。

大体积产物统一写到 `F:/AIScLocalArtifacts/memory-route/`。训练环境位于 `C:/Users/HP/.cache/AISc/memory-route/venv`；这是首次 smoke 已建立的例外，后续模型与实验产物不再写 C 盘。

## 固定入口

- `dataset_schema.json`：schema v1，训练标签只允许正式 `RetrievalDirection` 字段。
- `collect_route_dataset.py`：把候选方向送入正式 `DirectionResolver`；`--query-general-llm` 通过正式 `LlmDirectionProvider` 生成教师原始方向，并仅在离线入口叠加完整训练枚举白名单；传入隔离 engine factory 时只调用 `RetrievalEngine.probe()`。
- `train_route_lora.py`：assistant-only loss 的 BF16/NF4 LoRA 训练。
- `evaluate_route_specialist.py`：确定性字段级评估；传入隔离 engine factory 时补检索级 probe。
- `model_manifest.yaml`、`requirements-lock.txt`：底模、revision、许可和依赖锁定。
- `fixtures/smoke_candidates.jsonl`：仅用于模板、校准和反向传播 smoke 的脱敏夹具，不是人工批准的 golden corpus。
- `generate_synthetic_candidates.py`：生成 24 类、按 `source_group` 分组的脱敏合成候选、覆盖摘要和分层抽检；支持批次前缀、起始索引及与既有数据的冲突门禁，只生成本地候选，不调用教师模型。

## 数据审核

正式训练默认拒绝 `review.status != approved` 的样本。`--allow-unreviewed-smoke` 只允许验证模板、反向传播、Adapter 保存与重载，产物不得作为正式专项模型。相同 `source_group` 不得跨 split，标签中不得出现节点 ID 或边 ID。

所有中文输入通过 UTF-8 JSONL 文件传递。候选原始会话、真实存档、golden corpus、Adapter、checkpoint 和评估明细不得提交 Git，也不得上传外部服务。

## OpenAI-compatible 教师采集

教师密钥只从环境变量读取，不支持把密钥作为命令行参数写入 shell 历史。`--teacher-model` 使用服务商要求的模型名或部署 ID；先用 `--max-samples 1` 验证兼容性和费用，再扩大采集。输出仍是 `pending`，必须人工复核后才能成为 golden corpus。

教师采集每成功一条就追加 checkpoint；中途失败后使用完全相同的参数并增加 `--resume`，脚本会按 `sample_id` 跳过已完成记录。不要用 `--resume` 连接另一份候选文件，输出中存在未知样本时脚本会拒绝继续。

```powershell
$env:MEMORY_ROUTE_TEACHER_API_KEY = '<rotated-api-key>'
$python = 'C:\Users\HP\.cache\AISc\memory-route\venv\Scripts\python.exe'
& $python -m backend.training.memory_route.collect_route_dataset `
  --candidates F:\AIScLocalArtifacts\memory-route\datasets\candidates.jsonl `
  --output F:\AIScLocalArtifacts\memory-route\datasets\teacher_pending.jsonl `
  --query-general-llm `
  --teacher-base-url 'https://<workspace-host>/compatible-mode/v1' `
  --teacher-model '<model-name-or-deployment-id>' `
  --max-samples 1
Remove-Item Env:MEMORY_ROUTE_TEACHER_API_KEY
```

候选文件沿用 `fixtures/smoke_candidates.jsonl` 的逐行结构。真实对白或记忆在调用外部教师前必须先完成授权和脱敏；需要检索证据时另加 `--engine-factory module:function`，且该工厂只能连接隔离数据副本。

## 合成候选

```powershell
$python = 'C:\Users\HP\.cache\AISc\memory-route\venv\Scripts\python.exe'
& $python -m backend.training.memory_route.generate_synthetic_candidates `
  --output F:\AIScLocalArtifacts\memory-route\datasets\synthetic_candidates.jsonl `
  --count 384 `
  --batch-prefix synthetic-b02 `
  --start-index 97 `
  --existing-dataset F:\AIScLocalArtifacts\memory-route\datasets\synthetic_teacher_approved.jsonl
```

生成器同时写出 `.summary.json` 和 `.stratified_sample.jsonl`。摘要记录场景、mode、分组及新旧规范化输入、`sample_id`、`source_group` 冲突数；抽检文件按 24 类场景各取一条。所有记录仍只是 `candidate`，必须经过教师生成与人工复核。

已批准上传脱敏合成候选后，可批量生成教师标签：

```powershell
$env:MEMORY_ROUTE_TEACHER_API_KEY = '<rotated-api-key>'
& $python -m backend.training.memory_route.collect_route_dataset `
  --candidates F:\AIScLocalArtifacts\memory-route\datasets\synthetic_candidates.jsonl `
  --output F:\AIScLocalArtifacts\memory-route\datasets\synthetic_teacher_pending.jsonl `
  --query-general-llm `
  --teacher-base-url 'https://<workspace-host>/compatible-mode/v1' `
  --teacher-model '<available-model-name>'
```

## 环境与 smoke

```powershell
$python = 'C:\Users\HP\.cache\AISc\memory-route\venv\Scripts\python.exe'
$env:HF_HOME = 'F:\AIScLocalArtifacts\memory-route\huggingface'
& $python -m backend.training.memory_route.train_route_lora `
  --dataset F:\AIScLocalArtifacts\memory-route\datasets\reviewed.jsonl `
  --output F:\AIScLocalArtifacts\memory-route\artifacts\route-lora-smoke `
  --max-steps 1 --allow-unreviewed-smoke
```

采集或评估真实检索证据时，`--engine-factory module:function` 必须返回只连接隔离 SQLite/LanceDB 副本的 `RetrievalEngine`。需要 `llm_full_route` 教师证据时，工厂还必须给目标 mode 注入该策略。脚本只调用 `probe()`，但工厂仍有责任确保不会连接正式存档。
