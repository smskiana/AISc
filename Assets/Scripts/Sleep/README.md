# Sleep 脚本目录

## 文件夹功能

负责主动睡眠、23:30 强制睡眠、午夜结算、次日醒来与自动存档。

## 文件夹内容

- `SleepController`: 独立跨日状态机和十分钟现实超时。
- `SleepBedTrigger`: 玩家进入床位范围时发起一次主动睡眠确认，离开后才允许再次触发。

床位使用 `player_cafe.bed`，只供玩家使用，不参与 NPC affordance 或日程目标。
