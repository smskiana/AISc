# shared 目录说明

## 文件夹功能

保存 Unity 客户端与 Python 后端共同使用的稳定 ID 和基础语义配置。

## 文件夹内容

- `locations.json`: 地点、spot 稳定 ID 与 `spot_tags` affordance 标签。
- `actions.json`: 正式任务类型、动作语义与 `action_affordances`；移动方式不作为 action。
- `items.json`: 物品类型与物品语义。

修改共享配置时必须同步检查两端引用，并运行 `backend/scripts/check_project_conventions.py`。

NPC 正式任务禁止重新加入 `walk_to` / `run_to`。任务通过 `action_id + location_id + movement_mode` 表达“做什么、在哪里做、如何过去”。
