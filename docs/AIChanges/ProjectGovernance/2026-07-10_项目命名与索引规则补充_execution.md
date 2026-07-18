> 设计方案: [2026-07-10_项目命名与索引规则补充_plan.md](2026-07-10_项目命名与索引规则补充_plan.md)

# 项目命名与索引规则补充 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已在现有 `Unity MCP优先` 与 `GameObject命名规范` 之外，补上更广义的“项目命名与索引规范”：

1. 在 AI 规则中新增一条总规则
2. 明确跨端共享 ID 使用 `snake_case`
3. 明确显示名与程序 ID 分离
4. 明确 Python / C# 各自遵循本语言惯例
5. 明确 Unity 资源文件名与运行时 GameObject 命名分开管理
6. 明确新增核心文件后必须回写对应索引文档
7. 新建一份总规范文档作为统一入口

## 实际改动清单

### 修改文件 (2)

| 文件 | 实际改动 |
|------|------|
| `AGENTS.md` | 新增“项目命名与索引规范”条款，并顺延后续编号 |
| `CLAUDE.md` | 同步新增同口径规则，保持与 `AGENTS.md` 一致 |

### 新建文件 (3)

| 文件 | 说明 |
|------|------|
| `docs/DesignDocs/ProjectNamingAndIndexing.md` | 项目命名与索引总规范入口 |
| `docs/AIChanges/ProjectGovernance/2026-07-10_项目命名与索引规则补充_plan.md` | 本次方案文档 |
| `docs/AIChanges/ProjectGovernance/2026-07-10_项目命名与索引规则补充_execution.md` | 本执行记录 |

## 写入的核心规则

1. 跨端共享 ID 一律使用 `snake_case`
2. 显示名必须与程序 ID 分离
3. Python 命名遵循：
   - `snake_case`
   - `PascalCase`
   - `UPPER_SNAKE_CASE`
4. C# / Unity 命名遵循：
   - `PascalCase`
   - `camelCase`
5. Unity 资源文件名按“资源类型 + 业务对象”命名
6. 运行时 `GameObject` 命名继续由 `UnityNamingTags.md` 单独管理
7. 新增核心文件、核心配置、核心文档后，必须回写对应索引文档

## 新增文档内容

`docs/DesignDocs/ProjectNamingAndIndexing.md` 已覆盖：

- 跨端共享 ID 规则
- 显示名 / 程序 ID 分离
- Python 命名规则
- C# 命名规则
- Unity 资源文件命名规则
- GameObject 命名规则入口
- 核心文件索引规则
- 推荐索引文档位置

## 验证方式

- [x] 已确认 `AGENTS.md` 与 `CLAUDE.md` 规则文本一致
- [x] 已确认 `ProjectNamingAndIndexing.md` 成功创建
- [x] 已确认文档中包含命名规则与索引回写规则两大部分

## 本轮未做的事

1. 没有批量重命名现有脚本、Prefab、Scene 或 JSON 键
2. 没有立即创建全部推荐索引文档
3. 没有对历史文档中的旧命名做全面替换

这些属于后续可独立推进的“历史命名收敛 / 索引落地”工作。
