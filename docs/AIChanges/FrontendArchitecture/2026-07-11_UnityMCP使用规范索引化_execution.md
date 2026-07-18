> 设计方案: [2026-07-11_UnityMCP使用规范索引化_plan.md](2026-07-11_UnityMCP使用规范索引化_plan.md)

# Unity MCP 使用规范索引化 — 执行记录

## 完成时间

2026-07-11

## 本次完成内容

已将 Unity MCP 使用规范从主规则中的内联描述，整理为“独立规范文件 + 主规则入口 + 项目索引入口”的结构：

1. 新建独立规范文件，承接 Unity MCP 资产层规则与后续补充建议
2. 将 `AGENTS.md` / `CLAUDE.md` 的 Unity MCP 硬约束收口为入口式写法
3. 把新规范挂到项目总索引与设计文档索引
4. 将 `ProjectNamingAndIndexing.md` 中不属于命名规范的 Unity 资产层细则下沉为入口引用
5. 先落一条高频默认约定：中文 TMP 默认使用项目内 `MSYH SDF` 字体资产

## 实际改动清单

### 新建文件 (3)

| 文件 | 说明 |
|------|------|
| `docs/DesignDocs/UnityMCPUsageRules.md` | Unity MCP 使用规范主文档 |
| `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP使用规范索引化_plan.md` | 本次方案文档 |
| `docs/AIChanges/FrontendArchitecture/2026-07-11_UnityMCP使用规范索引化_execution.md` | 本执行记录 |

### 修改文件 (5)

| 文件 | 实际改动 |
|------|------|
| `AGENTS.md` | 将 Unity MCP 硬约束改为“摘要 + 明细入口” |
| `CLAUDE.md` | 同步 Unity MCP 明细入口 |
| `docs/ProjectIndex.md` | 新增 Unity MCP 规范入口 |
| `docs/DesignDocs/Index.md` | 新增 Unity MCP 规范入口 |
| `docs/DesignDocs/ProjectNamingAndIndexing.md` | 将 Unity 资产层 / MVC 细则改为入口式引用 |

## 新结构说明

### 1. 主规则

`AGENTS.md` / `CLAUDE.md` 继续保留：

1. Unity MCP 优先是硬约束
2. 资产层问题不能默认退回运行时代码

但不再在主规则里继续膨胀细则。

### 2. 独立规范文件

`docs/DesignDocs/UnityMCPUsageRules.md` 现在负责承载：

1. 适用范围
2. 资产层与运行时边界
3. 允许例外的条件
4. MVC 边界要求
5. Unity 侧默认约定
6. 后续追加规则的写法

### 3. 已落入的默认约定

本轮已先写入：

1. 中文 TMP 文本默认使用 `Assets/Fonts/MSYH SDF.asset`
2. 新建或复制中文 TMP 控件时，应优先在资产层完成字体替换

## 验证方式

- [x] 已确认 `AGENTS.md` 与 `CLAUDE.md` 均指向 `UnityMCPUsageRules.md`
- [x] 已确认 `docs/ProjectIndex.md` 与 `docs/DesignDocs/Index.md` 均新增入口
- [x] 已确认 `ProjectNamingAndIndexing.md` 不再承载大段 Unity MCP 细则
- [x] 已确认项目内存在 `Assets/Fonts/MSYH SDF.asset`，可作为中文 TMP 默认字体资产

## 未完成项

1. 本轮只完成规范收口，没有批量回收历史上已存在的默认 TMP 字体配置
2. 后续若再新增 Unity 场景、Prefab、UI、字体、连线等协作建议，应继续追加到 `docs/DesignDocs/UnityMCPUsageRules.md`

## 后续建议起点

若你接下来要继续补 Unity 侧要求，建议优先往这个文件追加：

- `docs/DesignDocs/UnityMCPUsageRules.md`

这样主规则可以继续保持短入口，细则则稳定累积在一个地方。
