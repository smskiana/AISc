# AIChanges 功能索引

## 作用

本索引只负责把任务路由到对应功能证据目录，不再按日期维护历史长表。进入目录后先读 README，再按主题关键词搜索 plan / execution。

| 功能目录 | 功能 | 内容 |
|----------|------|------|
| `ProjectGovernance/` | 项目治理 | 规则、索引、路线图、规范、架构治理和错误预防记录 |
| `Memory/` | 记忆系统 | 图记忆、向量数据层、检索、融合、印象和遗忘记录 |
| `Navigation/` | 导航系统 | A*、Anchor、传送、路径、移动结果和位置语义记录 |
| `NpcBehavior/` | NPC 行为 | 日计划、动作选择、空闲表现、名字牌和行为语义记录 |
| `Dialogue/` | 对话系统 | 对话流程、快捷回复、称呼、感知、气泡和对话 UI 记录 |
| `FrontendArchitecture/` | Unity 前端 | 职责拆分、场景、Prefab、UI、字体、视觉资产和生命周期记录 |
| `ProtocolAndIntegration/` | 协议与联调 | WebSocket、应用层接线、前后端协议和执行闭环记录 |
| `TestingAndDiagnostics/` | 测试与诊断 | 跑测、日志、性能、迁移验证和问题修复记录 |
| `Archive/Handoffs/` | 历史交接 | 旧 handoff，仅用于追溯，不代表当前口径 |
| `artifacts/` | 原始产物 | 日志、数据库、摘要和隔离测试产物 |

## 查找方式

1. 根据任务功能选择上表中的一个目录。
2. 阅读目录 README，确认内容边界。
3. 使用 `rg -n "主题关键词" docs/AIChanges/<功能目录>` 搜索。
4. 优先读取与任务最相关的 1-3 份记录，不按日期批量阅读。
5. 当前工程口径以 Workstream、ADR 和代码为准，execution 只作为实现证据。

## 维护规则

1. 新 plan / execution 直接创建在主要功能目录中，并在顶部互相索引。
2. 跨功能记录只存一份，按主要变更目标确定目录，其他功能 README 可以引用。
3. 禁止把 plan / execution / handoff 再放回 `docs/AIChanges/` 根目录。
4. 日期只保留在文件名中用于审计，目录和索引不得按日期组织。
5. 原始诊断产物继续放入 `artifacts/<功能标签>/`，不进入功能证据目录。
