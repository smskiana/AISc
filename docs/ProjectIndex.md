# 项目功能索引

## 作用

本文件是项目内容的总入口。查找内容时先判断任务属于哪个功能域，再进入对应目录的 `README.md` 或主索引；日期只用于审计，不用于导航。

## 项目目录

| 目录 | 功能 | 主要内容 | 入口 |
|------|------|----------|------|
| `Assets/` | Unity 客户端与游戏资产 | 脚本、场景、Prefab、UI、图片、字体和编辑器工具 | `Assets/README.md` |
| `backend/` | Python 游戏后端 | API、应用编排、NPC、对话、记忆、世界状态、存档、测试和脚本 | `backend/README.md` |
| `shared/` | 跨端共享配置 | 地点、spot tags、任务 affordance、物品稳定 ID 与基础语义 | `shared/README.md` |
| `docs/` | 项目知识与工程治理 | 路线图、工作流、ADR、设计文档、执行证据和问题记录 | `docs/README.md` |
| `Packages/` | Unity 包依赖 | Unity Package Manager 清单与锁定信息 | 非业务入口 |
| `ProjectSettings/` | Unity 项目设置 | 输入、渲染、标签、质量和编辑器设置 | 按具体 Unity 设置问题读取 |

## 功能入口

| 功能域 | 当前口径 | 代码 / 资产入口 | 历史证据 |
|--------|----------|-----------------|----------|
| 项目治理 | `docs/Workstreams/ProjectGovernance/README.md` | `AGENTS.md`、`docs/DesignDocs/ProjectNamingAndIndexing.md` | `docs/AIChanges/ProjectGovernance/README.md` |
| 记忆系统 | `docs/Workstreams/Memory/README.md` | `backend/src/memory/README.md` | `docs/AIChanges/Memory/README.md` |
| 导航系统 | `docs/Workstreams/Navigation/README.md` | `Assets/Scripts/Navigation/README.md`、`Assets/Scripts/UI/README.md` | `docs/AIChanges/Navigation/README.md` |
| NPC 行为 | `docs/Workstreams/NpcBehavior/README.md` | `backend/src/npc/README.md`、`Assets/Scripts/NPC/README.md` | `docs/AIChanges/NpcBehavior/README.md` |
| 对话系统 | `docs/Workstreams/Dialogue/README.md` | `backend/src/dialogue/README.md`、`Assets/Scripts/Dialogue/README.md` | `docs/AIChanges/Dialogue/README.md` |
| 前端架构 | `docs/Workstreams/FrontendArchitecture/README.md` | `Assets/Scripts/README.md` | `docs/AIChanges/FrontendArchitecture/README.md` |
| 协议与存档 | `docs/Workstreams/ProtocolAndSave/README.md` | `Assets/Scripts/Protocol/README.md`、`Assets/Scripts/Save/README.md`、`backend/src/protocol/README.md`、`backend/src/save/README.md` | `docs/AIChanges/ProtocolAndIntegration/README.md` |
| 测试与诊断 | `docs/Workstreams/TestingAndDiagnostics/README.md` | 按 Workstream 选择 Unity 测试、后端测试、跑测脚本或诊断工具 | `docs/AIChanges/TestingAndDiagnostics/README.md` |

## 文档功能入口

| 目录 / 文件 | 功能 | 内容 |
|-------------|------|------|
| `docs/Roadmap.md` | 项目路线 | 长期目标、当前阶段和冻结事项 |
| `docs/Workstreams/` | 当前工程口径 | 各功能域的状态、边界、下一步和相关入口 |
| `docs/DecisionRecords/` | 架构决策 | 已收敛且需要长期遵守的系统级决定 |
| `docs/DesignDocs/` | 设计与规范 | 系统设计、内容设计、命名规则和 Unity 规则 |
| `docs/AIChanges/` | 实现证据 | 按功能分类的 plan、execution、测试记录和历史交接 |
| `docs/KnownIssues.md` | 未解决问题 | 已知问题、暂缓事项和待验证风险 |

## AI 查找顺序

1. 读取 `AGENTS.md`。
2. 从本索引判断任务所属功能域。
3. 读取该功能域的 Workstream README 和代码目录 README。
4. 用 `rg` 搜索具体符号、配置键或业务关键词，建立最小调用链。
5. 只有涉及系统边界或既有决定时才读相关 ADR。
6. 只有需要追溯原因时才进入对应 `docs/AIChanges/<功能域>/`；不得先按日期浏览。
7. 只有任务涉及排期或跨系统影响时才读 `docs/Roadmap.md`。

## 索引维护原则

1. 目录按功能命名和划分，禁止新增日期目录、会话目录或“最新记录”目录。
2. 日期可以保留在执行证据文件名中，但只能作为审计元数据。
3. 新增功能目录时必须同时增加 README，并回写本索引或上级目录 README。
4. 普通叶子文件不进入总索引，由所属目录 README 或代码搜索负责定位。
