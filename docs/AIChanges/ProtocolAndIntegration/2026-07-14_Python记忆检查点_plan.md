# Python 记忆检查点设计方案

> 执行记录: [execution.md](2026-07-14_Python记忆检查点_execution.md)

## 需求理解

将 Python 现有“完整游戏存档”收缩为 AI 记忆检查点。检查点必须关联 Unity 提供的 `checkpoint_id`，并以临时目录、摘要和原子替换避免半份存档。

## Workstream / Roadmap

- Workstream: `ProtocolAndSave`
- Roadmap item: Python 记忆检查点原子化
- 相关 ADR: ADR-0006
- 工程口径变化: `SaveManager` 进入兼容适配期，新代码使用 `MemoryCheckpointService`

## 实现方案

1. 从运行 SQLite 导出记忆相关表到独立数据库，不复制世界状态表。
2. 同时复制 LanceDB，并为文件生成 SHA-256 摘要。
3. prepare 写临时目录，commit 原子替换正式检查点，abort 清理临时数据。
4. load 先在暂存区验证和迁移，commit 时才替换记忆数据。
5. 保留旧 `SaveManager` 供旧存档入口兼容，后续事务协议切换后停止使用。

## 风险点

1. 记忆表之间存在外键或隐式依赖，需要按真实 schema 选择表。
2. LanceDB 目录摘要必须递归稳定计算。
3. Windows 目录替换不能假设 POSIX rename 行为，需保留备份再交换。

## 验证

覆盖 prepare、commit、abort、摘要损坏、checkpoint 不匹配和世界表未进入记忆库。
