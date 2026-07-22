# 记忆系统执行证据

## 文件夹功能

保存记忆系统实现、修复和验证的 plan / execution。

## 文件夹内容

- 图记忆与向量数据层
- 记忆检索、融合、边语义和时间语义
- 玩家长期事实、夜间印象和遗忘机制

当前口径优先看 `docs/Workstreams/Memory/README.md` 和 ADR-0001。

## 相关执行记录

- [2026-07-21_记忆路由零LLM确定性查询切换_plan.md](2026-07-21_记忆路由零LLM确定性查询切换_plan.md)：基于 A/B/C 实验选择 C，把玩家默认切为 `local_only + [local]`、移除生产 R3 注册和预热，同时保留显式 R3/general 测试能力的唯一执行案。
- [2026-07-21_记忆路由零LLM确定性查询切换_execution.md](2026-07-21_记忆路由零LLM确定性查询切换_execution.md)：按唯一 plan 完成生产默认切换、显式 provider 测试注入和文档口径同步；结论为实现完成，待独立测试。
- [2026-07-21_记忆路由零LLM确定性查询切换_test.md](2026-07-21_记忆路由零LLM确定性查询切换_test.md)：独立测试会话入口，完成前不得认定整体切换验收通过。
- [2026-07-20_R3v2记忆路由运行时接入_plan.md](2026-07-20_R3v2记忆路由运行时接入_plan.md)：基于当前 `DirectionProvider`、严格 policy、`RetrievalEngine` 与 `GameRuntime` 生命周期设计 R3 v2 常驻 worker、可配置 provider chain、稳定回退和独立检索级验收的唯一执行案。
- [2026-07-20_R3v2记忆路由运行时接入_execution.md](2026-07-20_R3v2记忆路由运行时接入_execution.md)：完成配置 v2、共享 codec、Windows JSONL worker、provider runtime、engine/GameRuntime 减重接入与安全 trace；首次独立测试发现的隔离图资产缺失、CUDA 未早拒绝和关闭未唤醒问题已追加修复。
- [2026-07-20_R3v2记忆路由运行时接入_test.md](2026-07-20_R3v2记忆路由运行时接入_test.md)：初测暴露隔离图验收缺失、CUDA 未早期拒绝和 close 未唤醒在途请求；修复后有界复测已通过三 provider 真实隔离检索、权限、调用预算、无副作用、GPU 性能和故障矩阵，整体验收通过。
- [2026-07-20_记忆路由专项模型部署与训练_plan.md](2026-07-20_记忆路由专项模型部署与训练_plan.md)：Qwen3-0.6B Route LoRA 的本机离线部署、`llm_full_route` 教师证据、人工 golden corpus、SFT 与不接入正式 provider 的可行性验证方案。
- [2026-07-20_记忆路由专项模型部署与训练_execution.md](2026-07-20_记忆路由专项模型部署与训练_execution.md)：完成独立训练环境、R3 v2 / v3 SFT、冻结 test 字段级评估和实现期最低门禁；R3 v3 未提升总体质量且出现延迟异常，检索级评估仍待隔离图工厂。
- [2026-07-20_记忆路由专项模型部署与训练_test.md](2026-07-20_记忆路由专项模型部署与训练_test.md)：12 条冻结 test 的 LongCat-2.0、R3 v2 / v3 字段级对比及关闭 thinking 成对复跑；v3 总体质量无净提升且尾延迟较差，隔离检索与权限夹具缺失，完整验收尚未通过。

- [2026-07-17_玩家印象单目标并发午夜重构_execution.md](2026-07-17_玩家印象单目标并发午夜重构_execution.md)：午夜只刷新玩家印象、固定本地方向、提取并发、顺序提交、局部失败诊断和次日社交基线解耦。
- [2026-07-17_LLM定向本地深层记忆检索_execution.md](2026-07-17_LLM定向本地深层记忆检索_execution.md)：三策略 typed policy、LLM 方向解析、本地深搜、完全 LLM 路由、通用 trace 与 Unity 诊断控制同步。
- [2026-07-17_LLM检索想法向量路由修复_execution.md](2026-07-17_LLM检索想法向量路由修复_execution.md)：单次 query plan、本地方向校准、六分量原子条目选择、诊断 DTO 与验证同步。
