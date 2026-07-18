# 协议与联调执行证据

## 文件夹功能

保存 Unity 与 Python 后端之间的协议、连接和应用层接线记录。

## 文件夹内容

- WebSocket 连接与消息传输
- 后端应用层装配
- 前端命令、后端事件和执行结果回报
- NPC 正式任务的 `NPC_ACTION_RESULT` 终态与 `NPC_TASK_STATUS_QUERY / STATUS` 节点检测
- Unity 权威世界存档、Python 记忆检查点与 `checkpoint_id` 一致性协议
- NPC-NPC 社交 `PREPARE / READY / FAILED / COMPLETE` 会合与记忆提交闭环

当前入口是 `docs/Workstreams/ProtocolAndSave/README.md`、`Assets/Scripts/Core/`、`Assets/Scripts/Protocol/`、`Assets/Scripts/Save/`、`backend/src/protocol/`、`backend/src/save/` 和 `backend/src/application/`。

当前权威边界：NPC 任务成功只能由 Unity 终态或 Unity 保存的最近终态快照回报；后端预计时长不能推断成功，只负责节点询问、停滞检测和失联硬超时兜底。

存档权威边界：Unity 保存游戏世界事实，Python 保存 AI 记忆；Python 世界状态缓存不得反向覆盖 Unity 快照。

社交权威边界：Unity 决定 NPC 是否真实会合和气泡是否完整播放；Python 只在 READY 后生成、只在 COMPLETE 后提交记忆。旧 `NPC_SOCIAL_ACTION` 不是默认链路。

验证状态：协议与存档七批底座及 Play 回归均已完成。后续 AI 不应把保存、覆盖保存、读档、失败恢复或断线重连重新列为底座待验证项；只有新增玩法接入产生的新范围需要单独验证。
