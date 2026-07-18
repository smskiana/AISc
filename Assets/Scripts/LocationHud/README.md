# LocationHud 脚本目录

## 文件夹功能

负责将玩家内部 `location_id` 转换为大区域显示名并刷新 HUD。

## 文件夹内容

- `LocationHudModel`: 保存当前位置 ID 与玩家显示名。
- `LocationHudController`: 订阅玩家位置变化并更新 Model。
- `LocationHudView`: 只显示格式化后的地点文本。
