# Save 脚本目录

## 文件夹功能

负责 Unity 权威游戏世界存档的 DTO、schema migration、磁盘仓储和双端保存 / 加载协调。

## 文件夹内容

- `GameSaveData`: 稳定业务语义的世界快照。
- `UnitySaveRepository`: 临时写入、摘要校验和原子提交。
- `SaveMigrationRegistry`: 可扩展版本迁移链。
- `SaveCoordinator`: 与 Python 记忆检查点协议协调。

当前 Unity 主存档 schema 为 3；`GameSaveData` 默认版本、`UnitySaveRepository` 写入校验目标和 `SaveMigrationRegistry` 迁移终点必须同步更新。

开发期临时口径：开始菜单进入新游戏前调用 `UnitySaveService.PurgeAllForNewGame`，先通过 `new_game_backend_purge` 清除 Python 记忆检查点、可重建日程快照和日程幂等缓存，再清除 Unity `SaveData` 全部正式、备份和待提交目录；任一步失败均不进入新游戏。

不得把 UI、GameObject 引用、动画进度、正在移动或对话中的临时状态写入主存档。
