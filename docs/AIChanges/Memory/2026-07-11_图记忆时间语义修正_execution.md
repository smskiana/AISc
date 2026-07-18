> 设计方案: [2026-07-11_图记忆时间语义修正_plan.md](2026-07-11_图记忆时间语义修正_plan.md)

# 图记忆时间语义修正 — 执行记录

## 完成时间

2026-07-11

## 背景

上一版修复用 `PLAYER_FACT_BOUNDARY` 写死“玩家事实白名单”，可以临时防止 NPC 编造玩家行为，但长期不成立。

原因：

1. “小李准备重新开喫茶店”只是 Day 0 前后的听说/意图。
2. 后续玩家可能真的拿钥匙、打扫、挂招牌、开店。
3. 这些更新应该自然进入图和向量记忆，由时间顺序决定当前上下文，而不是额外建立僵硬事实库。

## 实际改动

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/src/dialogue/prompt_builder.py` | 移除硬编码 `PLAYER_FACT_BOUNDARY`，改为 `MEMORY_TIME_RULES`，要求 LLM 根据记忆时间判断先后 |
| `backend/src/npc/state_manager.py` | 初始共享玩家背景改为 Day 0/听说/当时状态语气，并写入 `created_day=0` |
| `backend/src/memory/retrieval.py` | 检索重建输出增加 `[Day 0]` / `[第N天]` 时间标签；Day 0 事件使用“听说/好像听说” |
| `backend/src/npc/npc_dialogue.py` | 收窄 `[FACT_GUARD]`，只拦亲历式玩家行动断言；带“听说/好像/不确定/准备”等语气的内容交给时间记忆判断 |
| `docs/AIChanges/Dialogue/2026-07-11_NPC对话玩家事实边界_execution.md` | 追加说明：硬白名单已被本轮替换 |
| `AGENTS.md` | 追加低级错误记录：Day 0 被 `or 1` 覆盖 |

### 新建文档

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/Memory/2026-07-11_图记忆时间语义修正_plan.md` | 本方案 |
| `docs/AIChanges/Memory/2026-07-11_图记忆时间语义修正_execution.md` | 本执行记录 |

## 关键实现

### 1. 初始背景回到图和向量系统

初始玩家背景不再在 prompt 中写死，而是作为 Day 0 记忆节点存在：

```text
Day 0 前后，街上听说小李准备重新开奶奶留下的喫茶店；这只是当时听到的打算，不代表之后的实际进展。
```

该节点仍会：

1. 写入 `memory_nodes`
2. 写入 LanceDB / SQLite 向量层
3. 连接到 `self` 和 `player person` 节点
4. 参与图路由、向量兜底、遗忘、融合

### 2. 检索上下文带时间标签

检索输出从：

```text
- 记得: 小李准备重新开奶奶留下的喫茶店
```

变为：

```text
- [Day 0] 听说: Day 0 前后，街上听说小李准备重新开奶奶留下的喫茶店；这只是当时听到的打算，不代表之后的实际进展。
```

后续如果第 5 天玩家真的完成开店相关行为，检索上下文可以同时出现：

```text
- [Day 0] 听说: 小李准备重新开喫茶店...
- [第5天] 记得: 小李今天把喫茶店招牌重新挂上了...
```

LLM 由此能按时间先后组织，而不是把 Day 0 当成永恒当前事实。

### 3. Prompt 改为通用记忆时间规则

`MEMORY_TIME_RULES` 现在强调：

1. 较新的记忆优先代表现在。
2. 较旧的记忆只代表当时知道的事。
3. “听说/准备/可能”不能改写成亲眼所见或已经完成。
4. 新记忆更新旧说法时，以新记忆为准。

### 4. `[FACT_GUARD]` 收窄

守门不再拦所有“喫茶店进展”传闻。

现在只替换：

1. “我看到小李在搬招牌”
2. “我刚帮小李搬东西”
3. “小李正在收拾店”

但不替换：

1. “听说那家喫茶店开始挂招牌了”
2. “听说小李准备重新开奶奶留下的喫茶店”

这样守门不再替代记忆系统，只负责避免亲历式幻觉污染短期记忆。

## 验证

### 1. Python 编译

执行：

```powershell
python -m py_compile backend/src/dialogue/prompt_builder.py backend/src/npc/state_manager.py backend/src/memory/retrieval.py backend/src/npc/npc_dialogue.py
```

结果：通过。

### 2. Day 0 格式化 smoke

执行 `RetrievalEngine._format_node_time({"created_day": 0})`。

结果：

```text
[Day 0]
```

### 3. 隔离冷启动检索 smoke

产物：

```text
docs/AIChanges/artifacts/2026-07-11_time_semantics_smoke2/retrieval.txt
```

内容确认：

```text
- [Day 0] 听说: Day 0 前后，街上听说小李准备重新开奶奶留下的喫茶店；这只是当时听到的打算，不代表之后的实际进展。
- [Day 0] 听说: Day 0 前，大家知道小李小时候就在樱桥通长大，后来去了城市。
- [Day 0] 好像听说: 樱桥通不大，街上几家店彼此都认识，谁家有点动静很快就会传开。
```

同时检查 LanceDB 原始行，玩家背景节点 `created_day=0`。

### 4. `[FACT_GUARD]` 收窄 smoke

会被替换：

```text
我刚才路过车站前，看到小李在搬招牌了，是不是真的要重开啦？
诶嘿嘿~今天去帮小李搬了点东西，路过这儿看见你在就想打个招呼！
```

不会被替换：

```text
听说那家喫茶店开始挂招牌了。
听说小李准备重新开奶奶留下的喫茶店。
```

### 5. 10 分钟后端观察跑测

为方便观察 NPC 气泡，本轮给 `backend/scripts/run_7day_benchmark.py` 增加了 `--player-location` 参数，默认仍为 `player_cafe.doorway`；本次跑测使用：

```powershell
python backend/scripts/run_7day_benchmark.py --max-runtime-sec 600 --player-location street.crossroad
```

最新有效产物：

```text
docs/AIChanges/artifacts/2026-07-11_time_semantics_10min_rerun2/2026-07-11_time_semantics_10min_rerun2.log
docs/AIChanges/artifacts/2026-07-11_time_semantics_10min_rerun2/2026-07-11_time_semantics_10min_rerun2_summary.json
```

关键结果：

| 指标 | 结果 |
|------|------|
| 实际运行 | 625.42 秒 |
| 结束原因 | `wall_time_reached` |
| 玩家位置 | `street.crossroad` |
| 游戏内推进 | 3240 分钟 |
| 最终时间 | 第3天 24:00 |
| `ERROR` | 0 |
| `WARNING` | 0 |
| `[FACT_GUARD]` | 0 |
| `NPC_BUBBLE` | 73 |
| `[MEMORY] retrieve` | 132 |
| `midnight_total` | 3 |
| 非法计划关键词 | 0 |
| 玩家搬招牌/搬桌子/亲眼看见类风险词 | 0 |

午夜耗时：

| 天数 | 午夜总耗时 |
|------|------------|
| Day 1 | 29.40 秒 |
| Day 2 | 31.45 秒 |
| Day 3 | 35.92 秒 |

观察结论：

1. 时间语义修改已正常应用，检索样本中出现 `[第1天]` 等时间标签。
2. 玩家位置移到 `street.crossroad` 后，10 分钟窗口内气泡量足够观察，共 73 条。
3. 未再发现“看到小李搬招牌 / 搬桌子”等未发生玩家行动的高风险台词。
4. 午夜处理仍是主要耗时点，但本轮目标是确认时间语义与玩家事实边界是否正常应用，性能优化另行跟进。

## 遇到的问题

### Day 0 被当作第 1 天

现象：

```text
- [第1天] 记得: Day 0 前后...
```

原因：

```python
node.get("created_day", 1) or 1
```

会把合法的 `0` 当成假值覆盖成 `1`。

修复：

1. 新增 `_node_created_day()`
2. 显式判断 `None`
3. 保留 `0` 作为合法时间值
4. 已同步记录到 `AGENTS.md` 低级错误记录

## 结论

本轮把玩家背景从“硬编码 prompt 事实白名单”改回“图 + 向量里的 Day 0 记忆”。

现在系统的方向是：

1. 初始背景是旧记忆，不是永久当前事实。
2. 后续玩家行动应该继续写入图/向量，成为更新的时间节点。
3. 检索时保留时间标签，让 LLM 可以按先后判断。
4. 输出守门只防亲历式幻觉，不替代图记忆系统。
