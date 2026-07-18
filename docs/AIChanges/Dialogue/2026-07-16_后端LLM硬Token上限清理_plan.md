# 后端 LLM 硬 Token 上限清理执行案

> 执行记录: [2026-07-16_后端LLM硬Token上限清理_execution.md](2026-07-16_后端LLM硬Token上限清理_execution.md)

## 需求理解

后端所有 LLM 业务调用不再传入 `max_tokens` 作为硬输出上限。输出长度、条目数量和格式通过 Prompt 软约束表达，最终安全性由既有解析、校验、截断和兜底逻辑保证，避免推理模型把预算消耗在 reasoning 后留下空正文或半截 JSON。

## 当前口径

1. 主要功能域为 Dialogue，同时影响 Memory 与 NpcBehavior 的 LLM 调用。
2. 不改变模型、供应商、temperature、协议、存档结构或 Unity 资产。
3. 不移除业务层的字符串截断、候选数量限制、JSON 校验和失败兜底。

## 实施步骤

1. 移除 `backend/src/` 下所有 LLM 调用传入的 `max_tokens` 参数。
2. 清理仅用于计算硬 token 上限的常量和说明，保留对话轮数、文本长度等业务约束。
3. 检查相关 Prompt 已表达输出格式、数量或长度要求；缺失时只补软约束。
4. 更新 Dialogue、Memory、NpcBehavior 的直接相关入口口径。
5. 执行 Python 编译、全量后端测试和静态残留检查。

## 涉及文件

- `backend/src/application/dialogue_service.py`
- `backend/src/memory/manager.py`
- `backend/src/memory/evolution.py`
- `backend/src/memory/retrieval.py`
- `backend/src/npc/npc_dialogue.py`
- `backend/src/npc/behavior_engine.py`
- `backend/src/npc/state_manager.py`
- 相关 Workstream / README 与 execution

## 风险与验收

1. 风险：模型可能输出冗长内容；由 Prompt 软约束及既有解析截断控制。
2. 风险：供应商无限生成增加延迟；本次遵循产品口径，不重新引入调用级硬 token 限制。
3. 验收：`backend/src/` 不再存在 `max_tokens=`；所有测试通过；相关文档明确采用软约束。
