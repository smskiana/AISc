# NPC 行为执行证据

## 文件夹功能

保存 NPC 行动规划、行为呈现和社交行为相关的 plan / execution。

## 文件夹内容

- 自主 NPC 与日常行为
- 地点、时间、身份和动作语义
- 空闲表现、名字牌后缀和行为状态
- 统一任务语义、action affordance、前端阶段执行与后端节点检测
- NPC-NPC 社交准备、真实移动终态、超时和终态后重新规划

当前口径优先看 `docs/Workstreams/NpcBehavior/README.md`。

当前社交闭环证据：`docs/AIChanges/ProtocolAndIntegration/2026-07-14_NPC社交协议闭环_execution.md`。

## 外界感知日程与互动重规划

- 执行方案：`docs/AIChanges/NpcBehavior/2026-07-17_外界感知日程与互动重规划_plan.md`
- 续接记录：`docs/AIChanges/NpcBehavior/2026-07-18_外界感知日程与互动重规划_execution.md`
- 结构化候选、供应商超时 fallback、Unity 切换裁决、剩余日程存读档、Unity 社交候选、运行时状态、`NpcStateEffect` 和互动后重规划源码迁移已接入；完整 Play Mode 存读档、跨日、社交锁和对话长链仍需在编辑器稳定运行时复测。

### 剩余迁移分阶段执行案

以下执行案按顺序实施；后一阶段以前一阶段通过验收为前置条件：

1. `2026-07-18_NPC运行时权威与社交协议收口_plan.md`：社交状态机、旧行为/时间/任务协议和后端全局业务时间镜像已收口；真实 Play Mode 社交失败与抢占长链仍待专项验证，详见对应 execution。
2. `2026-07-18_日程提交幂等与重连恢复_plan.md`：修复日程持久 revision、同日重连和后端重启幂等。
3. `2026-07-18_日程三层候选与记忆证据深化_plan.md`：完成物理过滤、图/向量证据、单次 LLM、最终校验与 fallback。
4. `2026-07-18_Unity日程执行压缩与重规划收口_plan.md`：完成 Unity 原子抢占、失败语义、17:00 压缩和局部重规划。
5. `2026-07-18_NPC日程诊断验收与协议清零_plan.md`：补齐诊断/控制探针、端到端验收、协议清零和索引更新。
