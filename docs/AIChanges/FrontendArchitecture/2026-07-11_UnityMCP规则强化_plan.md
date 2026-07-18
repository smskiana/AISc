> 执行记录: [2026-07-11_UnityMCP规则强化_execution.md](2026-07-11_UnityMCP规则强化_execution.md)

# Unity MCP 规则强化 — 设计方案

## 完成时间

2026-07-11

## 需求理解

用户指出：有些对话和实现仍然没有严格遵循“优先使用 Unity MCP 来维护 MVC 架构”的原则，希望把这条规则强化成更难被绕开的硬约束。

核心诉求不是重复“优先”二字，而是补齐：

1. 哪些问题默认必须走 Unity MCP
2. 哪些退回运行时代码的理由不再被接受
3. 真的需要例外时，需要满足什么门槛
4. 例外是否需要写进 plan / execution，避免后续会话继续沿着例外扩散

## 当前情况

现有规则已明确：

- 能由 Unity MCP 解决的场景 / 预制体 / 层级问题，优先在编辑器资产层完成
- 不要把资源配置问题写死进运行时代码

但当前仍有两个薄弱点：

1. “优先”偏软，容易在实际执行时被“先让它跑起来”绕过
2. 缺少例外治理机制，导致运行时兜底容易从临时方案变成长期结构

结合已有文档，特别是：

- `docs/AIChanges/FrontendArchitecture/2026-07-10_UnityMCP规则补充_execution.md`
- `docs/AIChanges/Dialogue/2026-07-10_对话UI预制体配置_execution.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-11_开始界面与后端启动_plan.md`

可以确认这个问题已经在 UI / 开始界面 / 场景配置场景中真实出现过。

## 本次修改范围

### 规则文件

- `AGENTS.md`
- `CLAUDE.md`

### 规范文档

- `docs/DesignDocs/ProjectNamingAndIndexing.md`

### 变更记录

- `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP规则强化_plan.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP规则强化_execution.md`

## 具体方案

### A. 强化 `AGENTS.md` / `CLAUDE.md` 中的 Unity MCP 规则

将原本偏“优先建议”的条款强化为：

1. 场景、Prefab、UI 层级、控件挂载、引用连线、编辑器生成流程这类资产层问题，默认必须先走 Unity MCP
2. 不允许以“先跑起来”“先临时做运行时 UI”“先写代码兜底”为默认方案
3. 只有同时满足以下条件，才允许例外进入运行时代码：
   - Unity MCP 当前无法稳定完成
   - 需求本质上属于运行时逻辑，而不是资源配置
   - 已在 plan / execution 中明确记录原因、边界和后续回收计划
4. 未记录例外理由时，视为违反 MVC 清洁边界

### B. 在总规范文档中同步补充执行口径

在 `ProjectNamingAndIndexing.md` 中增加一节或一段，明确：

1. Unity 资产层与运行时逻辑的边界
2. 哪些内容属于应由资产层承载的内容
3. 为什么运行时临时生成场景 / UI / 控件会污染 MVC
4. 例外需要“记录理由 + 限定范围 + 计划回收”

### C. 不在本轮处理历史实现

本轮只强化规则，不做：

- 对已有运行时兜底逻辑的大规模回收
- 对已有场景 / prefab / UI 代码的统一迁移
- 对历史 plan / execution 的追溯性改写

## 风险点

1. 规则过硬后，某些快速验证型原型会受到约束
2. 若例外条件写得不清，后续仍可能被“需求本质属于运行时逻辑”滥用
3. 若不把例外记录义务写明，后续会话仍然可能只在口头上说“临时”

## 处理策略

1. 保留有限例外，但要求写入 plan / execution
2. 把“先跑起来”明确列为不被接受的默认理由
3. 把“回收计划”写入规则，防止临时方案永久化

## 验证计划

1. `AGENTS.md` 与 `CLAUDE.md` 的强化版 Unity MCP 规则文本一致
2. `ProjectNamingAndIndexing.md` 中已出现更明确的 MVC / 资产层边界说明
3. 规则中已明确：
   - 默认必须先走 Unity MCP
   - 例外三条件
   - plan / execution 记录义务
