> 执行记录: [2026-07-10_GameObject命名规则补充_execution.md](2026-07-10_GameObject命名规则补充_execution.md)

# GameObject 命名规则补充 — 设计方案

## 完成时间

2026-07-10

## 需求理解

用户希望为“场景 / 预制体创建时的 GameObject 命名”补一条明确规则，要求：

1. 命名格式固定
2. 要能体现主要组件、用途、是否会被程序修改
3. 使用英文简写
4. 优先复用项目中已有的命名参考
5. 若现有文档没有对应缩写，需要先定义标签并写回文档，避免后续各起一套名字

用户给出的格式意图为：

- `主要组件（可空）_用途_状态标签`
- 示例：`btn_cancel_st`

## 当前情况

经检查：

1. `AGENTS.md` / `CLAUDE.md` 目前还没有 “GameObject 命名规范” 这一条
2. 项目中已有一些直观英文名称，如 `DialogueCanvas`、`ReplyPanel`、`SendButton`
3. 但没有一份统一的缩写标签文档来约束：
   - 组件前缀如何写
   - `static / dynamic` 的后缀如何写
   - 新缩写出现时写到哪里

因此这次除了补规则，还需要补一份轻量命名标签参考文档。

## 计划修改范围

### 规则文件

- `AGENTS.md`
- `CLAUDE.md`

### 设计文档

- `docs/DesignDocs/UnityNamingTags.md`（新增）

### 变更记录

- `docs/AIChanges/FrontendArchitecture/2026-07-10_GameObject命名规则补充_plan.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_GameObject命名规则补充_execution.md`

## 具体方案

### A. 在规则中新增命名规范条款

写入以下核心约束：

1. 新建场景对象、预制体根节点与子节点时，命名遵循：
   - `<component?>_<purpose>_<state>`
2. `component` 使用英文缩写，可为空
3. `purpose` 使用英文小写语义词，采用下划线分隔
4. `state` 固定为：
   - `st` = static，不会被程序动态修改
   - `dy` = dynamic，会被程序动态修改
5. 如果 `component` 为空，则直接使用：
   - `<purpose>_<state>`
6. 生成场景 / 预制体时优先复用文档中已登记的缩写标签
7. 如果必须新增缩写，先补进命名标签文档，再使用

### B. 新增命名标签文档

创建一份简短但可扩展的参考文档，先登记：

1. 本次必须固定的状态标签：
   - `st`
   - `dy`
2. 若干高频组件标签，供 Unity MCP / 后续手工搭建统一复用，例如：
   - `btn`
   - `pnl`
   - `txt`
   - `img`
   - `inp`
   - `spr`
   - `cvs`
   - `go`
   - `anc`

这份文档不追求一次性列全，只提供“已批准缩写表”和“新增缩写回填规则”。

### C. 不在本轮顺手批量重命名旧资产

本轮目标是先建立规则入口，不把范围扩散到：

- 既有 prefab 批量改名
- 既有 scene 层级全面清洗
- 脚本里所有字符串引用同步迁移

后续若要清历史命名债，应单独开一轮并配合 Unity MCP / 引用校验处理。

## 风险点

1. 现有资产仍包含 PascalCase 或自然语言命名，短期内会与新规范并存
2. 若未来新增过多缩写但不回填文档，会再次失控
3. 若把“dynamic”误解为“会激活/隐藏”而不是“会被程序改动”，执行时会产生歧义

## 处理策略

1. 规则仅强制约束“新建 / 新生成”的对象
2. 文档明确 `dy` 的判断标准是“程序运行中会主动改名、改状态、改内容、改层级或改引用相关表现”
3. 缩写新增必须先登记后使用

## 验证计划

1. `AGENTS.md` 与 `CLAUDE.md` 均新增同口径命名规则
2. `docs/DesignDocs/UnityNamingTags.md` 成功创建
3. 文档中已明确：
   - 命名格式
   - `st / dy` 含义
   - 高频标签示例
   - 新缩写回填流程
