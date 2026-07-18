# 导航传送点配置执行记录

## 实际改动清单

1. `Assets/Data/Nav_Map/NavGrid_Main.asset`
   - 从场景对象 `go_tranport_st` 读取 8 组传送点。
   - 写入 `NavigationGridAsset._teleportLinks`。
   - 每条传送点均设置为双向、启用、触发半径 `0.35`、通行成本 `1.0`。

2. `Assets/Scenes/Town_Main.scene`
   - 将 `go_tranport_st/go_streetWagashi_st/bookStore_st` 重命名为 `wagashi_st`，避免和旧书店传送点混淆。

## 已配置传送点

1. `street_cafe`
   - street: `(1.988451, -2.741696)`
   - cafe: `(-11.996549, -4.738696)`

2. `street_bookstore`
   - street: `(2.488451, 1.0283041)`
   - bookstore: `(13.708451, 1.260304)`

3. `street_park`
   - street: `(8.068451, 0.03830397)`
   - park: `(4.718451, 8.458303)`

4. `street_bridge`
   - street: `(-6.091549, 0.04830396)`
   - bridge: `(0.978451, 16.608303)`

5. `street_police_box`
   - street: `(6.478451, 0.878304)`
   - police box: `(12.904451, -4.455696)`

6. `street_wagashi`
   - street: `(5.758451, -2.951696)`
   - wagashi: `(13.462451, -1.372696)`

7. `street_flower_shop`
   - street: `(-0.72254896, 1.1933041)`
   - flower shop: `(-11.415549, -0.44369602)`

8. `street_bakery`
   - street: `(-1.9075489, -2.7686958)`
   - bakery: `(-11.451549, 4.1633043)`

## 验证方式

1. 通过 Unity MCP 读取 `go_tranport_st` 及其 8 组子物体坐标。
2. 使用 `manage_scriptable_object` dry run 验证 `NavGrid_Main.asset` 的 `_teleportLinks` 字段路径。
3. 应用 patch 后读取 `Assets/Data/Nav_Map/NavGrid_Main.asset`，确认 8 条 `_teleportLinks` 已写入。
4. 保存 `Town_Main.scene`。

## 注意事项

1. Unity Console 仅出现一条 MCP WebSocket 初始化 warning，与项目脚本无关。
2. 仍建议后续用 `NpcNavigationDebugController` 在 Play 模式控制 NPC 跨区域移动，确认 A* 实际会使用这些传送 link。
