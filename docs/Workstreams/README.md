# 工作流索引

## 作用

`docs/Workstreams/` 是项目路线图和具体执行记录之间的中间层。

每个工作流 README 只维护系统级状态，不复制执行记录全文。

## 当前工作流

| 工作流 | 作用 | 入口 |
|--------|------|------|
| 项目治理 | 功能目录、AI 查找规则、ADR、Roadmap 与执行证据管理 | `ProjectGovernance/README.md` |
| 记忆系统 | 图记忆、向量数据层、检索、遗忘、夜间印象 | `Memory/README.md` |
| 导航系统 | A*、typed path、NPC 传送、玩家场景入口、SceneAnchor、移动结果与 transit | `Navigation/README.md` |
| NPC 行为 | 正式任务语义、affordance、前端终态、节点检测与空闲表现 | `NpcBehavior/README.md` |
| 对话系统 | 玩家对话、NPC 闲聊、现场感知、快捷回复与准备握手 | `Dialogue/README.md` |
| 前端职责 | Unity Core / NPC / Dialogue / Navigation 职责拆分与回归 | `FrontendArchitecture/README.md` |
| 协议与存档 | 协议 envelope、记忆检查点、Unity 主存档、重连和状态迁移 | `ProtocolAndSave/README.md` |

## 维护规则

1. 新增长期方向时，优先新增或更新工作流 README。
2. 单次执行记录只在必要时回链到工作流，不把流水账复制进工作流。
3. 如果一个执行记录推翻了既有工程口径，应同步新增或更新 ADR。
4. 如果只是普通 bug 修复，在对应功能证据目录记录即可；`ChangeIndex.md` 只维护功能入口，不维护单条记录。
