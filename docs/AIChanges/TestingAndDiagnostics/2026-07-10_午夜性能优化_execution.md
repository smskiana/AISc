> 设计方案: [2026-07-10_午夜性能优化_plan.md](2026-07-10_午夜性能优化_plan.md)

# 午夜性能优化 — 执行记录

## 完成时间
2026-07-10

## 本次完成内容

本次没有改记忆语义，只针对午夜性能热点做了第一轮优化，重点落在三件事上：

1. embedding 模型真正统一复用
2. 图提取改成批量编码
3. 夜间熟人印象生成改成有界并发

另外，运行时午夜链路补上了阶段耗时日志，并把最重的同步阶段移到线程侧执行，便于后续继续观察。

## 实际改动文件

### 代码文件 (4)

| 文件 | 实际改动 |
|------|------|
| `backend/src/memory/embedding.py` | 为全局 BGE 模型缓存增加初始化锁；保证并发首次访问时不重复建模；`encode_batch()` 支持空输入并明确返回 512 维向量矩阵 |
| `backend/src/memory/manager.py` | 去掉按节点单独建模编码的旧路径；`extract_and_ingest()` 改为先收集节点文本，再一次性 `encode_batch()` 后统一写入 LanceDB |
| `backend/src/npc/state_manager.py` | 夜间刷新增加目标人物查询向量缓存；熟人印象生成改成“预处理 + 有界线程池并发 + 顺序写库”；`_graph_target_memories()` 支持复用外部传入查询向量 |
| `backend/src/application/runtime.py` | 午夜流程增加分阶段耗时日志；演化阶段和夜间印象/状态结算改为 `asyncio.to_thread(...)` 执行，减少主事件循环阻塞 |

### 文档文件 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/TestingAndDiagnostics/2026-07-10_午夜性能优化_plan.md` | 本次实施方案 |
| `docs/AIChanges/TestingAndDiagnostics/2026-07-10_午夜性能优化_execution.md` | 本执行记录 |

## 关键实现说明

### 1. embedding 复用现在真正收口了

之前最伤的一点是：

- 业务层还在绕过公共 embedding 入口，自己 new `SentenceTransformer`

现在改成：

- 所有新增编码都走 `embedding.py`
- 全局模型使用单例缓存
- 首次并发访问时用锁保护，避免重复初始化

额外做了一个小验证：

- 同一进程里连续两次 `_get_model()` 返回的是同一个对象

### 2. 图提取从“逐节点编码”改成了“批量编码”

之前 `extract_and_ingest()` 的问题是：

- 每个新节点单独编码一次

现在的路径变成：

1. 先把本轮要写入的 LanceDB 节点收集起来
2. 把 `value` 文本列表一次性交给 `encode_batch()`
3. 再按顺序把向量回填回节点
4. 最后统一 `upsert_nodes()`

这一步是对午夜提取阶段最直接的一次本地侧降耗。

### 3. 夜间印象生成改成了有界并发

之前 `nightly_refresh()` 对每个 `owner -> target` 都是串行跑：

1. 查近期互动
2. 查图片段
3. 调 LLM
4. 写库

现在调整为：

1. 先顺序准备任务输入
2. 先把目标人物查询向量统一算好
3. 并发跑 LLM 基准印象生成
4. 全部结果回收后再顺序写入数据库

这样做保住了两个目标：

1. LLM 请求可以并发缩短总耗时
2. 数据库写入仍保持可追踪、可排查

### 4. 午夜运行时增加了可观测性

现在午夜流程会分别记录：

1. 边衰减耗时
2. 事件提取耗时
3. 图演化耗时
4. 印象/状态结算耗时
5. 短期记忆清理耗时
6. 午夜总耗时

这让后续即使还没开始新一轮 7 天长测，也能先在正常运行日志里看出瓶颈主要落在哪一段。

## 验证结果

### 已完成验证

- [x] Python 编译检查通过：
  - `backend/src/memory/embedding.py`
  - `backend/src/memory/manager.py`
  - `backend/src/npc/state_manager.py`
  - `backend/src/application/runtime.py`

- [x] 导入检查通过：
  - `import src.main`
  - 返回 `import-ok`

- [x] 状态层 smoke test 通过：
  - 新建临时 SQLite
  - 执行 `StateManager.cold_start()`
  - 执行 `nightly_refresh(1)`
  - 执行 `begin_new_day("sakura")`
  - 返回 `smoke-ok`

- [x] embedding 复用验证通过：
  - 同一进程连续两次 `_get_model()`
  - 返回 `same-model True`

- [x] 图提取批量编码路径验证通过：
  - 用 Dummy LLM + Dummy LanceDB 跑 `extract_and_ingest()`
  - 返回 `written 2`
  - LanceDB 接收到 `2` 个节点
  - 两个节点向量长度均为 `512`

### 本轮未做

- [ ] 新一轮 7 天压测
- [ ] 午夜前后 `/api/health` 响应对比
- [ ] 与修改前日志做量化耗时对照

这些按用户要求暂时搁置，先停在“完成优化实现和基础验证”。

## 当前判断

这轮优化已经把最明显的几个低效点处理掉了：

1. 重复建模
2. 逐节点 embedding
3. 夜间印象串行 LLM
4. 午夜缺乏阶段耗时可观测性

所以现在的状态是：

- 代码层面的第一轮性能优化已经落地
- 基础功能未被打断
- 是否带来多大幅度的实际耗时下降，还需要下一轮长跑或午夜日志对照来确认

## 后续建议

下一步最值得做的不是继续盲改，而是：

1. 跑一次新的午夜或 7 天压测
2. 对照新的午夜阶段日志
3. 再决定是否继续优化：
   - `short_term_memories` 读取重复
   - 图片段检索的批量化
   - 演化阶段并行度
   - LLM 并发上限调优
