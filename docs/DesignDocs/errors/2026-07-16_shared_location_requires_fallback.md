# 共享地点新增后缺少 Unity fallback

## 错误现象

在 `shared/locations.json` 新增 `player_cafe.bed` 后，`backend/scripts/check_project_conventions.py` 报告 `location_positions` 缺少同一 `location_id`。

## 根本原因

共享地点稳定 ID 同时服务于协议语义、场景 Anchor 和 Unity 无 Anchor 时的坐标 fallback。本轮只先更新了共享语义，遗漏了 `Assets/Resources/Config/location_positions.json` 的兼容入口。

## 正确做法

新增或删除共享地点时同步检查：

1. `shared/locations.json` 的 zone / spot 定义。
2. Unity 场景中的 `SceneAnchor`。
3. `Assets/Resources/Config/location_positions.json` 的同 ID fallback。
4. 运行 `backend/scripts/check_project_conventions.py`，不得只依赖场景中当前存在 Anchor。

## 适用范围

地点、床位、传送出口、任务目标点和其他需要跨 Unity / Python 传递的稳定 `location_id`。
