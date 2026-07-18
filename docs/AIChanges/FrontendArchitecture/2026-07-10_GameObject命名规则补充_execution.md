> 设计方案: [2026-07-10_GameObject命名规则补充_plan.md](2026-07-10_GameObject命名规则补充_plan.md)

# GameObject 命名规则补充 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已为 Unity 场景 / 预制体创建补充正式的 GameObject 命名规则，并建立统一的标签登记文档：

1. 在项目 AI 规则中新增 “GameObject 命名规范” 条款
2. 将命名格式固定为：
   - `<component?>_<purpose>_<state>`
3. 固定状态标签：
   - `st` = static
   - `dy` = dynamic
4. 新增独立命名标签参考文档，供 Unity MCP 和后续人工搭建统一复用

## 实际改动清单

### 修改文件 (2)

| 文件 | 实际改动 |
|------|------|
| `AGENTS.md` | 在“核心行为底线”中新增 GameObject 命名规范，并顺延后续编号 |
| `CLAUDE.md` | 同步新增同口径命名规范，保持与 `AGENTS.md` 一致 |

### 新建文件 (3)

| 文件 | 说明 |
|------|------|
| `docs/DesignDocs/UnityNamingTags.md` | Unity 场景 / Prefab GameObject 命名标签参考 |
| `docs/AIChanges/FrontendArchitecture/2026-07-10_GameObject命名规则补充_plan.md` | 本次方案文档 |
| `docs/AIChanges/FrontendArchitecture/2026-07-10_GameObject命名规则补充_execution.md` | 本执行记录 |

## 写入的核心规则

1. 新建场景对象、Prefab 根节点与子节点时，命名遵循：
   - `<component?>_<purpose>_<state>`
2. `component` 使用主要组件英文缩写，可为空
3. `purpose` 使用英文小写语义词，并采用下划线分隔
4. `state` 固定使用：
   - `st`：不会被程序修改
   - `dy`：会被程序修改
5. 若没有明确组件前缀，则直接使用：
   - `<purpose>_<state>`
6. 新缩写必须先补进命名标签文档，再投入使用

## 新增文档内容

`docs/DesignDocs/UnityNamingTags.md` 已登记：

- 状态标签：
  - `st`
  - `dy`
- 常用组件标签：
  - `btn`
  - `pnl`
  - `txt`
  - `img`
  - `inp`
  - `spr`
  - `cvs`
  - `anc`
  - `go`

## 验证方式

- [x] 已确认 `AGENTS.md` 与 `CLAUDE.md` 新规则文本一致
- [x] 已确认 `UnityNamingTags.md` 成功创建
- [x] 已确认文档中包含命名格式、状态标签、常用组件标签与新增标签回填规则

## 本轮未做的事

1. 没有顺手批量重命名既有 prefab / scene 对象
2. 没有同步修改脚本内现有字符串查找路径
3. 没有把历史 PascalCase 命名一次性迁到新规范

这些属于后续可单独开的一轮“历史命名收敛”工作，不和本次规则建立混在一起。
