# 代码大局观文档执行记录

## 实际改动清单

1. 新增 `docs/DesignDocs/CodebaseBigPicture.md`
   - 说明项目代码层面的总体架构。
   - 梳理 Unity / backend / shared 的主关系。
   - 补充启动连接、消息分发、NPC 行为、NPC 社交、导航传送等关键数据流。
   - 明确 Core、NPC、Navigation、Dialogue、后端运行时、NPC 行为、对话、记忆系统的职责边界。
   - 记录当前过重类：
     - `GameManager`
     - `AStarMovementProvider`
     - `NpcBubbleManager`
     - `PortraitDialogueUI`
   - 补充新功能进入规则和导航问题阅读链路。

2. 更新 `docs/ProjectIndex.md`
   - 将 `docs/DesignDocs/CodebaseBigPicture.md` 加入新会话推荐阅读顺序。
   - 将代码大局观文档加入规范与检查入口。

3. 更新 `docs/DesignDocs/Index.md`
   - 将 `CodebaseBigPicture.md` 登记为高频核心设计文档。

## 验证方式

1. 静态检查文档链接和相对路径。
2. 本轮为文档补齐，不涉及代码编译。

## 未完成项

1. 尚未执行 `docs/AIChanges/FrontendArchitecture/2026-07-12_前端职责框架整改_plan.md` 中的第一阶段代码重构。
2. 后续若继续重构，应优先从 typed navigation path 和 `NavigationTeleportLink` 自主管理容差开始。
