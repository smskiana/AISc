# Save 模块

## 文件夹功能

负责 Python AI 记忆检查点的写入、读取、兼容和运行时恢复。

## 文件夹内容

`MemoryCheckpointService` 只保存记忆表与 LanceDB，并通过 `checkpoint_id` 与 Unity 主存档关联。旧 `SaveManager` 暂时保留为完整存档兼容适配器，不作为新功能入口。

开发期临时支持 `memory_checkpoints_purge_all`：仅由 Unity 新游戏入口调用，永久删除全部正式、备份和待提交记忆检查点；清理失败会返回失败响应并阻止 Unity 进入新游戏。
