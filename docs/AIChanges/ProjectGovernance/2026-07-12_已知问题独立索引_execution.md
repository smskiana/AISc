> 设计方案: [2026-07-12_已知问题独立索引_plan.md](2026-07-12_已知问题独立索引_plan.md)

# 已知问题独立索引执行记录

## Workstream

ProjectGovernance / Navigation

## Roadmap item

GOV / NAV

## 相关 ADR

1. `docs/DecisionRecords/ADR-0002-navigation-typed-path.md`

## 实际改动清单

### 1. 新增全局已知问题索引

新增 `docs/KnownIssues.md`：

1. 记录当前仍存在、暂缓处理或待进一步验证的问题。
2. 明确它不替代 `docs/DesignDocs/ErrorPreventionIndex.md`。
3. 记录首个已知问题：
   - `NAV-LOW-001`：传送稳定但入口触发偏宽。

### 2. 导航工作流改为引用 KnownIssues

更新 `docs/Workstreams/Navigation/README.md`：

1. 删除局部重复的已知问题完整描述。
2. 保留 `docs/KnownIssues.md` 链接。
3. 保留当前登记条目摘要：`NAV-LOW-001`。

### 3. 回写项目入口和变更索引

更新：

1. `docs/ProjectIndex.md`
   - 在规范与检查入口中登记 `docs/KnownIssues.md`。
2. `docs/AIChanges/ChangeIndex.md`
   - 在项目治理分组登记本轮“已知问题独立索引”。

## 验证方式

1. 静态检查 `docs/KnownIssues.md` 存在。
2. 静态检查 `docs/Workstreams/Navigation/README.md` 已指向 `docs/KnownIssues.md`。
3. 静态检查 `docs/ProjectIndex.md` 已登记 `docs/KnownIssues.md`。
4. 静态检查 `docs/AIChanges/ChangeIndex.md` 已登记本执行记录。

本轮只修改文档，不涉及代码编译。

## 未完成项

1. 未修复 `NAV-LOW-001`。
2. 未调整任何传送点半径或 Unity 资产配置。
