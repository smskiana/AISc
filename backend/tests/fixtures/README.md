# 后端脱敏测试夹具

本目录保存可提交、无正式存档内容的固定测试输入。

`route_runtime_corpus.jsonl` 只与 `backend.tests.route_runtime_isolated_factory:create_engine` 配套使用。每条记录显式声明隔离数据、正式 `RetrievalRequest`、必须命中的节点和禁止跨 NPC 命中的私有节点；节点内容均为合成文本，不包含真实会话或记忆。

运行时检索独立验收应分别传入 `--provider r3_v2`、`general_llm` 和 `local`。factory 每次在 OS 临时目录创建新的 SQLite/LanceDB，不连接 `backend/data`、SaveData 或任何正式存档。
