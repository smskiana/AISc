> 执行记录: [2026-07-12_UnityLayoutGroup提醒_execution.md](2026-07-12_UnityLayoutGroup提醒_execution.md)

# Unity Layout Group 使用提醒 — 设计方案

## 需求理解

用户希望在 `Unity MCP` 使用规范中补一条明确提醒：

1. 当使用 Unity 自带 `Layout Group` 排布 UI 时
2. 如果希望子物体维持预期形状和尺寸
3. 需要给对应子物体补 `Layout Element`
4. 否则容易出现子物体被压扁、被挤成一团的问题

## 方案思路

1. 在 `docs/DesignDocs/UnityMCPUsageRules.md` 的“默认约定”下新增 `Layout Group` 提醒小节
2. 用“默认做法 + 风险现象 + 执行要求”的写法记录这条经验
3. 补一份 execution，保证后续会话能从 `docs/AIChanges/` 追到这次规则追加

## 涉及文件

预计修改：

1. `docs/DesignDocs/UnityMCPUsageRules.md`

预计新增：

1. `docs/AIChanges/FrontendArchitecture/2026-07-12_UnityLayoutGroup提醒_plan.md`
2. `docs/AIChanges/FrontendArchitecture/2026-07-12_UnityLayoutGroup提醒_execution.md`

## 风险点

1. 若只写“要加 Layout Element”而不说明适用场景，后续可能被机械化滥用
2. 若不点明“想保持子物体形状/尺寸”这一前提，规则会显得过硬且不准确

## 本轮目标

1. 把这条 UI 踩坑经验沉淀到 Unity MCP 规范中
2. 保持主规则不变长
3. 让后续资产层 UI 调整更少重复踩坑
