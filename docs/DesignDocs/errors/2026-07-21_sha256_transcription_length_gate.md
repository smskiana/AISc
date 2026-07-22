# SHA-256 抄录缺位但未在冻结时拦截

## 错误现象

R3 v2 Adapter 的 SHA-256 从训练记录复制到运行时接入草案和 plan 时，在 `509bf7bbdcced` 片段少抄一个 `d`，形成只有 63 位的文本。运行时实现会话执行严格的 64 位格式校验后，聚焦测试出现 15 passed、3 failed，并按 plan 停止条件撤销代码改动。

## 根本原因

资产身份冻结依赖人工目视复制，记录链只检查“多个文档中的文本是否一致”，没有在首次写入和后续转录时同时执行两项独立门禁：SHA-256 格式必须是 64 位小写十六进制，以及记录值必须与目标实物重新计算结果完全一致。错误值因此能在 plan、Workstream 草案和训练 execution/test 之间保持一致，却不代表它正确。

## 正确做法

1. 冻结 SHA-256 前直接对最终目标文件执行 `Get-FileHash -Algorithm SHA256` 或等价标准库计算，不从日志片段、终端换行或另一份文档二次转录。
2. 写入文档、配置或 manifest 前先验证 `^[0-9a-f]{64}$`，再与实物复算值做逐字符相等比较；两道门禁缺一不可。
3. 同一哈希复制到 plan、execution、test 和配置时，以已复算的单一值为来源，并在最低门禁中全仓库搜索旧错误值和同资产的分叉值。
4. 严格校验失败时保留失败，不放宽长度或字符集规则；先回到方案会话纠正冻结身份，再开启新的执行会话。

## 本次修正

已对 `F:/AIScLocalArtifacts/memory-route/artifacts/route-lora-r3-v2-approved-480/adapter/adapter_model.safetensors` 重新计算 SHA-256，确认文件大小为 40,422,168 bytes，64 位结果为 `cd2676f7f64f28a351fb35b2d2d76fa01b30662a509bf7bbddcced6f9cf92b8d`。随后同步修正运行时 Workstream 草案、原 plan 以及关联训练 execution/test 中的全部错误副本；未放宽运行时严格校验，也未恢复已撤销的代码改动。
