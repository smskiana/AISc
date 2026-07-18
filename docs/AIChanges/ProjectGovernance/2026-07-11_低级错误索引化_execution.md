> 设计方案: [2026-07-11_低级错误索引化_plan.md](2026-07-11_低级错误索引化_plan.md)

# 低级错误索引化 — 执行记录

## 完成时间

2026-07-11

## 本次完成内容

已将“低级错误记录”从规则文件内联堆积，改为“索引 + 单条明细”的结构：

1. `AGENTS.md` / `CLAUDE.md` 不再直接堆错误细节
2. 新增独立错误索引文件
3. 为当前已有错误建立独立明细文档
4. 把入口同步挂到项目索引和设计文档索引

## 实际改动清单

### 修改文件 (4)

| 文件 | 实际改动 |
|------|------|
| `AGENTS.md` | 将“低级错误预防”改为入口式写法，不再直接承载错误细节 |
| `CLAUDE.md` | 同步改为入口式写法 |
| `docs/DesignDocs/Index.md` | 新增 `ErrorPreventionIndex.md` 入口 |
| `docs/ProjectIndex.md` | 新增低级错误索引入口与说明 |

### 新建文件 (4)

| 文件 | 说明 |
|------|------|
| `docs/DesignDocs/ErrorPreventionIndex.md` | 低级错误总索引 |
| `docs/DesignDocs/errors/2026-07-11_day0_or1_override.md` | 当前已有错误的完整明细 |
| `docs/AIChanges/ProjectGovernance/2026-07-11_低级错误索引化_plan.md` | 本次方案文档 |
| `docs/AIChanges/ProjectGovernance/2026-07-11_低级错误索引化_execution.md` | 本执行记录 |

## 新结构说明

### 规则文件

现在只保留：

1. 出错后要记录
2. 记录方式是“独立明细 + 回写索引”
3. 后续修改前优先回看索引

### 索引文件

`docs/DesignDocs/ErrorPreventionIndex.md` 负责：

1. 汇总错误条目
2. 提供一句话摘要
3. 标注影响范围
4. 指向具体明细文档

### 明细文件

单条错误文档负责完整保留：

1. 现象
2. 根因
3. 错误模式
4. 正确做法
5. 适用范围
6. 修改前自查点

## 验证方式

- [x] 已确认 `AGENTS.md` 与 `CLAUDE.md` 不再直接堆错误细节
- [x] 已确认 `ErrorPreventionIndex.md` 成功创建
- [x] 已确认 `Day 0 / or 1` 错误已有独立明细文件
- [x] 已确认 `docs/DesignDocs/Index.md` 与 `docs/ProjectIndex.md` 均能指向该索引

## 未完成项

1. 历史上若再发现其他可复用错误，后续需要按相同结构继续补充

当前结构已经建立，后面只需要往索引和明细里继续追加，不必再把规则文件写长。
