# 玩家基础 UI 与日常闭环执行记录

> 设计方案: [plan.md](2026-07-16_玩家基础UI与日常闭环_plan.md)

## 本轮范围

按用户确认的开发期临时策略，实现“每次进入新游戏前永久删除全部 Unity 存档及 Python 记忆检查点”。本轮只实现新游戏清档闭环，不宣称整个玩家基础 UI 与日常闭环 plan 已完成。

## 实际改动

1. Python `MemoryCheckpointService` 新增幂等 `purge_all`，删除正式、`.previous` 和 `.pending` 检查点后重建空根目录。
2. 协议新增 `memory_checkpoints_purge_all`、`memory_checkpoints_purged_all` 和 `memory_checkpoints_purge_all_failed`。
3. Unity `UnitySaveRepository` 新增全仓储清理；`UnitySaveService` 先清 Python，确认成功后再清 Unity，并通过事件报告结果。
4. 开始菜单在双端清理成功后才调用 `StartNewGameFlow`；失败时恢复按钮并留在菜单。
5. `aisc_debug.runtime_snapshot.save` 新增 `is_purging_for_new_game` 和 `last_new_game_purge_error`，协议轨迹同时可观察请求 ID、阶段和失败响应。
6. 新增 Python 测试，覆盖正式、备份、待提交检查点的永久清理和清理后继续可用的目录结构。

## 文档与边界

1. 已回写前端 plan、协议与存档 Workstream、Unity / Python Save README 和前端执行证据入口。
2. 未修改 ADR：Unity 世界存档权威与 Python 记忆检查点权威边界不变，只新增新游戏前的破坏性协调操作。
3. 不涉及场景、Prefab、SerializeField 或 UI 资产连线，因此本轮不需要 Unity MCP 资产修改。

## 验证

1. `python -m unittest backend.tests.test_memory_checkpoint -v`：6 项通过。
2. `pytest` 在当前 Python 环境不可用（未安装模块），已改用标准库 `unittest` 执行同一测试文件。
3. `dotnet build Assembly-CSharp.csproj --no-restore -v:minimal`：编译成功，0 error；9 个 warning 均为既有程序集版本冲突或未赋值字段。
4. 尚需 Unity MCP Play 验收：准备至少一个手动槽、自动槽和 Python 检查点，点击新游戏后确认列表为空、目录已删除且新世界正常进入；再用 `aisc_debug` 检查清理状态与协议轨迹。

## 未完成项

1. 整体玩家基础 UI 与日常闭环 plan 的其他阶段仍按原方案继续。
2. 正式恢复多存档产品流程时，必须显式移除“新游戏先清空全部存档”的临时策略及对应提示文案。
