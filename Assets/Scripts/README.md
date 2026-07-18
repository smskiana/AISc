# Unity 脚本目录说明

## 文件夹功能

保存 Unity 客户端运行时与编辑器脚本。详细核心文件入口见 `Index.md`。

## 文件夹内容

- `Core/`: 生命周期、全局状态、命令和 WebSocket。
- `Data/`: 客户端数据结构与配置模型。
- `Dialogue/`: 对话流程与对话数据适配。
- `Navigation/`: 寻路、移动、Anchor 和传送。
- `NPC/`: NPC 实体、生成、正式任务状态机、行为呈现和空闲表现。
- `UI/`: 界面控制器与通用 UI。
- `Editor/`: Unity 编辑器构建和配置工具。
- `Diagnostics/`: 面向 AI、编辑器工具和自动测试的结构化运行时诊断。
- `Pause/`: 多来源暂停、Gameplay/UI/FX 三时间域策略与 FX 适配器。
