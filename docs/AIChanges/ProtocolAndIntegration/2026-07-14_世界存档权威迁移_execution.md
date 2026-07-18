# 世界存档权威迁移执行记录

> 设计方案: [plan.md](2026-07-14_世界存档权威迁移_plan.md)

## 实际改动

1. Unity 本地 `manifest.json` 成为存档列表与读档 checkpoint 身份入口。
2. 开始菜单经 `GameManager` facade 读取 Unity 本地存档列表。
3. Unity 主存档持久化时间、天气、玩家地点和 NPC 世界事实。
4. 读档完成直接发出兼容 `GAME_READY` 事件，不再调用 Python `CONTINUE` 覆盖 Unity 状态。
5. Python 世界表保留为运行时推理缓存和旧协议兼容，不再进入新记忆检查点。
6. 双端提交增加 previous、finalize 和 abort rollback，避免一端提交失败留下错配。

## 兼容边界

1. Python `SaveManager` 和旧 `SAVE_REQUEST / LOAD_REQUEST / GET_SAVES` 暂时保留，供旧客户端兼容。
2. 当前玩家背包模型已预留 Unity DTO，但现有 `GameStateStore` 尚无正式背包运行模型，因此本轮不会伪造背包内容。
3. Python 运行时仍缓存时间和 NPC 状态用于行为与记忆推理；持久化权威已迁到 Unity。

## 验证

1. `python -m unittest discover -s backend/tests -v`: 27 项通过。
2. `python -m compileall -q backend/src backend/tests`: 通过。
3. `python backend/scripts/check_project_conventions.py`: 通过。
4. Unity MCP 全量刷新和编译：Console 0 error。
5. Unity EditMode 测试任务成功，但项目当前实际用例为 0 项。

## 未完成项

1. 玩家背包、货币和任务系统出现正式运行模型后，应接入已预留的 Unity 存档 DTO。

## 后续验证状态

用户已确认协议与存档底座 Play 回归完成，包括真实保存、覆盖保存、读档、失败恢复和断线重连。本文原“尚需 Play 验证”事项已关闭，不再代表当前状态。
