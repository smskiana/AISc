# Navigation 脚本目录

## 文件夹功能

保存 Unity 侧路径规划、角色移动、场景 Anchor 和传送逻辑。

## 文件夹内容

包括 A*、移动提供者、导航网格、传送点和移动结果语义。当前边界见 Navigation Workstream 和 ADR-0002。

## 玩家传送入口

- `PlayerTeleportController.cs`: 复用 `NavigationTeleportPoint` 检测最近入口、显示交互提示并执行玩家传送。
- `PlayerLocationResolver.cs`: 从 `SceneAnchorRegistry` 解析并同步玩家当前 `location_id`。
