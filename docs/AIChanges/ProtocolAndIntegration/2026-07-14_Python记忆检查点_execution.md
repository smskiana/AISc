# Python 记忆检查点执行记录

> 设计方案: [plan.md](2026-07-14_Python记忆检查点_plan.md)

## 实际改动

1. 新增 `MemoryCheckpointService`，支持 prepare / commit / abort / load。
2. 记忆检查点保留记忆、羁绊、印象和诊断表，排除 NPC 即时状态、背包和游戏状态表。
3. SQLite 使用热备份，LanceDB 目录同步复制，全部文件使用 SHA-256 manifest 校验。
4. 加载只在事务内替换记忆表，不覆盖 Unity 权威世界表。
5. 旧 `SaveManager` 保留为兼容适配器。

## 验证

1. `python -m unittest backend.tests.test_memory_checkpoint -v`: 3 项通过。
2. `python -m compileall -q backend/src backend/tests`: 通过。

## 未完成项

记忆检查点尚未接入 WebSocket 保存 / 加载事务，留待批次 5。
