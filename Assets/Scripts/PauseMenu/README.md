# PauseMenu 脚本目录

## 文件夹功能

负责游戏内 `Esc` 菜单、设置占位页、返回开始菜单和退出桌面流程。

## 文件夹内容

- `PauseMenuController`: 处理输入、确认流程与保存后退出编排。
- `PauseMenuView`: 管理主菜单和设置页的资产化控件。

存档列表和事务由 `SaveManagementController` 负责，本模块不复制存档逻辑。
