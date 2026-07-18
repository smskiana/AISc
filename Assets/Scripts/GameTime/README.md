# GameTime 脚本目录

## 文件夹功能

负责 Unity 权威游戏时间、时间 HUD 和昼夜表现，不承载睡眠或午夜结算流程。

## 文件夹内容

- `GameTimeModel`: 保存并推进天、小时、分钟和天气。
- `GameTimeController`: 驱动时间、响应加载和暂停、同步 Python 镜像。
- `GameTimeView`: 格式化玩家 HUD。
- `DayNightView`: 将当前时间映射为 24 个整点颜色节点之间的平滑插值。

Python 不再维护镜像时钟或分钟推进循环。冻结时间随日计划、对话、社交决策、互动重规划和午夜请求显式发送；`GAME_TIME_SYNC`、`GAME_PAUSE_STATE` 与 `FAST_FORWARD` 已废弃并从 Unity sender 删除。
