> 设计方案: [2026-07-12_UnityLayoutGroup提醒_plan.md](2026-07-12_UnityLayoutGroup提醒_plan.md)

# Unity Layout Group 使用提醒 — 执行记录

## 完成时间

2026-07-12

## 本次完成内容

已在 `Unity MCP` 使用规范中补充 `Layout Group` 相关提醒：

1. 使用 Unity 自带 `Layout Group` 时
2. 若希望子物体保持预期尺寸与形状
3. 默认需要为子物体补 `Layout Element`
4. 避免因缺少布局信息导致子物体被压缩、挤成一团

## 实际改动清单

### 新建文件 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/FrontendArchitecture/2026-07-12_UnityLayoutGroup提醒_plan.md` | 本次方案文档 |
| `docs/AIChanges/FrontendArchitecture/2026-07-12_UnityLayoutGroup提醒_execution.md` | 本执行记录 |

### 修改文件 (1)

| 文件 | 实际改动 |
|------|------|
| `docs/DesignDocs/UnityMCPUsageRules.md` | 新增 `Layout Group` 使用提醒小节 |

## 验证方式

- [x] 已确认规则补充落在 `UnityMCPUsageRules.md`，未继续膨胀主规则
- [x] 已明确记录“使用 Layout Group 且希望维持子物体形状/尺寸”这一适用前提
- [x] 已明确记录缺少 `Layout Element` 的典型风险现象

## 未完成项

1. 本轮只补规范提醒，没有批量回查历史 UI 预制体中缺失的 `Layout Element`

## 后续建议起点

若后续继续补 Unity UI 相关提醒，可继续追加到：

- `docs/DesignDocs/UnityMCPUsageRules.md`
