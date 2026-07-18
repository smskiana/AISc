# 重连与世界快照执行记录

> 设计方案: [plan.md](2026-07-14_重连与世界快照_plan.md)

## 实际改动

1. Unity 在 `hello_ack` 后自动发送全量世界快照。
2. Python 只用快照覆盖推理缓存中的时间、玩家位置和 NPC 世界事实。
3. 握手时清理玩家对话准备态、活跃态和 NPC 未确认任务追踪。
4. 世界快照带 revision 和 checkpoint 身份，Python 返回应用结果。

## 边界

1. LLM 流、移动过程和 UI 不恢复。
2. Python 缓存不反向覆盖 Unity。
