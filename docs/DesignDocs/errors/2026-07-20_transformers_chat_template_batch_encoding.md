# Transformers 5 chat template 返回 BatchEncoding

## 错误现象

在 Transformers 5.14.1 中调用 `tokenizer.apply_chat_template(..., return_tensors="pt")` 后，把返回值直接传给 `model.generate(inputs)`，生成阶段因对象没有 tensor `shape` 而失败。

## 根本原因

当前 API 在组合 `return_tensors="pt"` 与 `return_dict=True` 时返回 `BatchEncoding`，其中 tensor 位于 `input_ids`、`attention_mask` 等字段。旧示例把返回值视作单一 tensor，和当前版本的返回契约不一致。

## 正确做法

1. 显式设置 `return_dict=True`。
2. 把整个批次移动到设备后使用 `model.generate(**inputs)`。
3. 用 `inputs["input_ids"].shape[-1]` 计算 prompt 长度。
4. smoke 必须覆盖 tokenizer、关闭 thinking、生成和 decode 整条链，而不能只验证模型加载。

## 本次修正

记忆路由 BF16 与 NF4 smoke 改用 `BatchEncoding` 展开调用，模型生成均成功。正式工具中的评估路径同样采用 `model.generate(**inputs)`。

