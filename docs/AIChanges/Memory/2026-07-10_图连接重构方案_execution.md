> 设计方案: [2026-07-10_图连接重构方案_plan.md](2026-07-10_图连接重构方案_plan.md)

# 图连接重构方案 — 执行记录

## 完成时间
2026-07-10

## 本次完成内容

本次没有改代码，只完成了“图连接重构方案”的书面方案整理，并按当前项目实现重新对齐了问题边界。

方案重点覆盖了：

1. 当前图的真实生成/更新/检索流程
2. 新旧节点连接现状
3. 边方向与检索方向错位的问题
4. 节点复用、补边、融合继承的重构方向
5. 分阶段实施顺序与验证计划

## 新增文件

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-10_图连接重构方案_plan.md` | 本次完整重构方案 |
| `docs/AIChanges/Memory/2026-07-10_图连接重构方案_execution.md` | 本执行记录 |

## 方案依据

本次方案不是脱离现有项目重写，而是基于以下实现链路梳理后得出的：

1. 初始图创建：
   - `backend/src/npc/state_manager.py`

2. 午夜短期记忆提取入图：
   - `backend/src/memory/manager.py`
   - `backend/src/application/runtime.py`

3. 图检索：
   - `backend/src/memory/retrieval.py`

4. 图融合：
   - `backend/src/memory/evolution.py`

5. 图基础表结构：
   - `backend/src/database/sqlite_client.py`
   - `backend/src/database/lancedb_client.py`

同时也参考了已有设计文档和历史方案，尤其是：

1. `docs/DesignDocs/memory/graph-memory-model.md`
2. `docs/DesignDocs/MemoryArchitecture.md`
3. `docs/AIChanges/Memory/2026-07-08_BGE向量图记忆系统_plan.md`

## 当前结论摘要

方案中确认的核心问题有四类：

1. 新旧节点连接过于依赖 LLM 自由输出
2. 建边方向和检索起点方向错位
3. 旧节点复用机制不稳定
4. 融合节点不继承旧边

因此方案把重构目标定义为：

- 让后端重新接管“节点复用、结构补边、融合继承、可达性设计”

## 说明

这次按用户要求先“直接写计划”，所以当前停在方案阶段，没有继续进入代码实施。
