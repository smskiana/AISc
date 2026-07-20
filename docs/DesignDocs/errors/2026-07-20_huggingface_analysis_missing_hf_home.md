# Hugging Face 分析命令漏传 HF_HOME

## 错误现象

专项模型正式评估已把 `HF_HOME` 指向 F 盘，但后续只读 tokenizer 统计命令没有继承该环境变量。`AutoTokenizer.from_pretrained()` 因而回退到用户默认缓存，在 `C:/Users/HP/.cache/huggingface/hub/` 新建约 15.9 MB 的 Qwen tokenizer 缓存，并尝试访问 Hugging Face Hub。

## 根本原因

把“只加载 tokenizer 做报告分析”误认为不会产生缓存写入，环境约束只写在正式训练/评估命令中，没有覆盖临时 Python 分析子进程。Transformers / huggingface_hub 的缓存位置由进程环境决定；即使模型权重已在 F 盘，未设置 `HF_HOME` 的新进程仍会使用默认 C 盘目录。

## 正确做法

1. 任何调用 `AutoTokenizer.from_pretrained()`、`AutoModel.from_pretrained()` 或 Hugging Face Hub API 的训练、测试、分析命令，都必须在启动 Python 前显式设置 `HF_HOME=F:/AIScLocalArtifacts/memory-route/huggingface`。
2. 只读复核既有资产时同时使用 `local_files_only=True`，避免缓存缺失时静默访问网络或创建另一份缓存。
3. 命令结束后检查输出中的 Hub 警告，并核对项目约定的缓存根；不能只检查模型权重产物目录。
4. 不把临时分析命令视为缓存规则例外，也不依赖上一个 shell 或子进程残留的环境变量。

## 本次修正

发现后确认默认缓存目录创建于本次命令，包含 8 个文件、共 15,881,798 字节；模型正式评估报告不受影响。已验证待清理路径严格位于 Hugging Face hub 下，但环境安全策略两次阻止递归删除，因此没有绕过策略强删，残留路径已写入独立测试记录。后续专项模型命令统一显式设置 F 盘 `HF_HOME`，只读分析增加 `local_files_only=True`。
