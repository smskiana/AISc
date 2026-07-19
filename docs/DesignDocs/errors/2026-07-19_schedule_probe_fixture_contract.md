# 日程探针夹具必须命中目标契约层

## 现象

迟到 revision 探针先使用 `0`，命中了 `invalid_schedule_revision`；固定 planner 探针又假设候选 ID 为 `routine_0`，实际正式候选使用稳定哈希，因而进入 fallback。

## 根本原因

探针夹具绕过了目标 seam 的前置契约：revision 必须先合法才会判断陈旧，candidate ID 必须来自正式 Prompt adapter 输出。

## 正确做法

1. 验证 stale revision 时先接收 revision 2，再提交合法但陈旧的 revision 1。
2. 固定 provider 从传入的紧凑候选标签读取稳定 ID，不在探针中猜测内部 ID 生成规则。
3. 同时断言稳定原因和隔离写入范围，避免“失败了就算通过”的假阳性。

## 影响范围

日程 revision、planner provider、受控 DTO/标签 adapter 及其他需要命中特定拒绝层的诊断探针。
