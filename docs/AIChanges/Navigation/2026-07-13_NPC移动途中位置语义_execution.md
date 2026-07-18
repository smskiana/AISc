# NPC 移动途中位置语义执行记录

> 设计方案: [plan.md](2026-07-13_NPC移动途中位置语义_plan.md)

## 实际改动

1. 新增内部 transit 位置语义：`__transit__:<npc_id>:<request_id>`。
2. `npc_states` 新增：
   - `movement_origin`
   - `movement_target`
   - `movement_status`
3. 发出移动行为时：
   - 保存最后确认的出发地和目标地。
   - 设置 `movement_status = moving`。
   - 将 `current_location` 改为本次请求唯一的 transit 标记。
4. 移动成功后提交 Unity 实际位置并清空移动字段；失败或取消后恢复 Unity 实际位置或原出发地。
5. proximity 层对 transit 位置统一返回“不在同区、不邻近”，包括同一个 transit 标记与自身比较。
6. 玩家正式对话和建议回复 Prompt 将移动中位置渲染为：
   - `从<出发地>到<目标地>的途中（移动中，不属于任何地区）`
7. transit 状态不加载出发地或目标地的固定物件、气味、spot 和地区现场感知。
8. NPC-NPC 对话行为摘要也能显示途中描述；正常社交检测会因 transit 不同区而阻止移动中 NPC 触发会面。

## 涉及文件

- `backend/src/world/location_state.py`
- `backend/src/world/proximity.py`
- `backend/src/database/sqlite_client.py`
- `backend/src/npc/behavior_engine.py`
- `backend/src/dialogue/prompt_builder.py`
- `backend/src/dialogue/perception_context.py`
- `backend/tests/test_protocol_execution_loop.py`

## 验证

1. `python -m unittest discover -s backend/tests -v`: 10 项通过。
2. 临时 SQLite 数据库初始化与迁移检查：通过，三个移动字段存在。
3. `python -m compileall -q backend/src backend/tests`: 通过。
4. `dotnet build AISc.sln --no-restore`: 通过，0 error；保留项目既有程序集版本警告。
5. `python backend/scripts/check_project_conventions.py`: 通过。

## 遇到的问题

新增测试类时，补丁插入点使两个原有测试方法落入了错误类。已调整类边界，并记录到低级错误预防索引。

## 未完成项

1. 尚未在 Unity Play 模式观察移动开始、成功、取消时后端日志与 Prompt 实际文本。
2. 存档或断线恰好发生在 transit 状态时，当前会保存内部途中标记；重连后的移动恢复或回退策略仍需随重连快照协议设计。
3. Unity 本地 `NpcEntity.CurrentLocation` 仍保存最后到达地点，transit 是后端权威语义；前端若需要展示“途中”UI，后续应增加独立移动状态字段，不能用 transit ID 寻路。
