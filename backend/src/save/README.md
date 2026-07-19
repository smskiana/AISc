# Save 模块

## 文件夹功能

负责 Python AI 记忆检查点的写入、读取、兼容和运行时恢复。

## 文件夹内容

`MemoryCheckpointService` 只保存记忆表与 LanceDB，并通过 `checkpoint_id` 与 Unity 主存档关联。旧 `SaveManager` 暂时保留为完整存档兼容适配器，不作为新功能入口。

开发期由 `new_game_backend_purge.py` 提供新游戏复合清理 seam：统一删除记忆检查点和可重建日程快照并清空日程内存幂等缓存；检查点子步骤失败时恢复本次日程删除，返回稳定子域失败码并阻止 Unity 进入新游戏。`memory_checkpoints_purge_all` 只作为协议兼容入口。
