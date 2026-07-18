# Core 脚本目录

## 文件夹功能

保存 Unity 客户端主生命周期、连接、命令发送和运行状态管理代码。

## 文件夹内容

包括 `GameManager`、`GameCommandSender`、`GameStateStore`、`WebSocketClient`、玩家控制及后端进程托管。连接、协议入口或全局状态问题先从本目录定位。

NPC 正式任务协议由 Core 负责路由和发送，但任务生命周期属于 `Assets/Scripts/NPC/NpcTaskExecutor.cs`，不得把阶段状态机塞进 `GameManager`。
