> 设计方案: [2026-07-11_UnityMCP规则强化_plan.md](2026-07-11_UnityMCP规则强化_plan.md)

# Unity MCP 规则强化 — 执行记录

## 完成时间

2026-07-11

## 本次完成内容

已将原本偏“优先建议”的 Unity MCP 规则强化为更明确的硬约束，重点补上了例外门槛和记录义务：

1. 场景 / Prefab / UI / 引用连线等资产层问题默认必须先走 Unity MCP
2. “先跑起来”“先运行时代码兜底”不再被视为默认可接受方案
3. 只有满足明确条件，才允许例外进入运行时代码
4. 若例外未写进 `plan / execution`，则视为未遵守规则

## 实际改动清单

### 修改文件 (3)

| 文件 | 实际改动 |
|------|------|
| `AGENTS.md` | 将第 6 条升级为“Unity MCP优先（硬约束）”，补充资产层问题范围、禁止性表述与例外三条件 |
| `CLAUDE.md` | 同步强化同口径规则，保持与 `AGENTS.md` 一致 |
| `docs/DesignDocs/ProjectNamingAndIndexing.md` | 新增“Unity 资产层与 MVC 边界”章节，明确资产层/运行时职责分界与例外记录要求 |

### 新建文件 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP规则强化_plan.md` | 本次规则强化方案 |
| `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP规则强化_execution.md` | 本执行记录 |

## 写入的核心规则

1. 场景、Prefab、UI 层级、控件摆放、组件挂载、SerializeField 连线这类问题，默认属于资产层配置问题
2. 资产层配置问题默认必须先走 Unity MCP，而不是退回运行时代码
3. “先跑起来”“先临时运行时创建 UI / 节点 / 控件”“先代码兜底”不再是默认可接受理由
4. 只有同时满足以下条件，才允许例外：
   - Unity MCP 当前无法稳定完成
   - 需求本质属于运行时逻辑
   - 已在 `plan / execution` 中记录原因、范围与回收计划
5. 未记录例外理由时，视为未遵守本规则

## 验证方式

- [x] 已确认 `AGENTS.md` 与 `CLAUDE.md` 强化版规则文本一致
- [x] 已确认 `ProjectNamingAndIndexing.md` 新增 MVC / 资产层边界说明
- [x] 已确认规则中包含例外三条件与文档记录义务

## 未完成项

1. 本轮没有回收历史上已经存在的运行时兜底实现
2. 本轮没有追溯修改旧执行记录中的临时方案表述

这些如果要继续收口，建议单独开一轮“历史运行时兜底回收”。
