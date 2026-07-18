# 记忆系统执行证据

## 文件夹功能

保存记忆系统实现、修复和验证的 plan / execution。

## 文件夹内容

- 图记忆与向量数据层
- 记忆检索、融合、边语义和时间语义
- 玩家长期事实、夜间印象和遗忘机制

当前口径优先看 `docs/Workstreams/Memory/README.md` 和 ADR-0001。

## 相关执行记录

- [2026-07-17_玩家印象单目标并发午夜重构_execution.md](2026-07-17_玩家印象单目标并发午夜重构_execution.md)：午夜只刷新玩家印象、固定本地方向、提取并发、顺序提交、局部失败诊断和次日社交基线解耦。
- [2026-07-17_LLM定向本地深层记忆检索_execution.md](2026-07-17_LLM定向本地深层记忆检索_execution.md)：三策略 typed policy、LLM 方向解析、本地深搜、完全 LLM 路由、通用 trace 与 Unity 诊断控制同步。
- [2026-07-17_LLM检索想法向量路由修复_execution.md](2026-07-17_LLM检索想法向量路由修复_execution.md)：单次 query plan、本地方向校准、六分量原子条目选择、诊断 DTO 与验证同步。
