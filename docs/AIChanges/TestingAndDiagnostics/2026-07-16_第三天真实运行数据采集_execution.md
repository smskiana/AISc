> 设计方案: [2026-07-16_第三天真实运行数据采集_plan.md](2026-07-16_第三天真实运行数据采集_plan.md)

# 第三天真实运行数据采集 - 执行记录

## 运行过程

1. 通过 Unity MCP 进入 `Town_Main` Play 模式。
2. 调用现有 `GameManager.StartNewGameFlow()` 开始新游戏，未使用 `FAST_FORWARD`，未直接设置日期或时间。
3. 从 Day 1 08:00 连续运行至 Day 3 07:04，经历两次正常午夜结算和醒来流程。
4. 玩家主要在街道活动，并由用户人工移动、触发对话以增加真实数据。
5. 持续使用 `aisc_debug.runtime_snapshot` 与 `health_report` 检查时间、位置、对话、暂停、连接和 NPC 任务状态。

## 运行中观察

1. Day 1 22:31 玩家在街道与九条进入正式对话，时间按设计暂停。
2. Day 2 醒来后一度因 wake anchor / 位置解析进入其他区域；测试期间曾短暂固定玩家到街道，用户开始手动操作后立即恢复 `PlayerController`。
3. Day 2 23:22 NPC 正在执行睡眠或当日收尾任务。
4. Day 3 07:04 最终抓取窗口：雨天、玩家位于 `street.crossroad`、与九条对话中、健康状态 `ready`。

## 采集产物

产物目录：`docs/AIChanges/artifacts/memory_route_day3_source/`

1. `game_day3.db`：通过 SQLite Backup API 生成的一致副本。
2. `lancedb/`：Day 3 抓取窗口的向量库副本。
3. `manifest.json`：运行快照、数据库统计、检索分布、边类型、LanceDB 表行数和 SHA-256。

## 数据规模

| 数据 | 数量 |
|---|---:|
| 图节点 | 100 |
| 图边 | 109 |
| 短期记忆 | 20 |
| 检索日志 | 191 |
| NPC 印象 | 25 |
| 融合来源 | 0 |
| LanceDB 表 | 6 |
| LanceDB 行 | 110 |

短期记忆：`behavior=10`、`interaction=10`。

检索模式：

| 模式 | 次数 | LLM 路由调用 | 本地跳过 | 平均耗时 |
|---|---:|---:|---:|---:|
| nightly_impression | 175 | 172 | 140 | 1.216s |
| player_dialogue | 14 | 15 | 3 | 2.233s |
| npc_dialogue | 2 | 2 | 0 | 0.755s |

## 重要口径

1. Unity/后端镜像运行快照是 Day 3 07:04；SQLite `game_state` 的时间字段仍显示 Day 1 08:00，说明该表不是当前 Unity 权威时间来源。后续测试必须使用 `manifest.runtime_snapshot` 作为时间上下文。
2. `npc_dialogue` 只有 2 条检索记录，符合运行中观察到的 NPC 主动移动和社交不足；不能用这部分小样本独立得出稳定广度/深度结论。
3. 玩家对话和夜间印象数据量已经明显高于此前初始数据，可作为下一轮主要测试来源。

## 验证

1. Day 3 抓取时 `aisc_debug.health_report.status=ready`。
2. SQLite 副本可正常打开并查询全部 12 个表。
3. LanceDB 副本可打开 6 个表并读取行数。
4. `game_day3.db` SHA-256：`7f5ac0aaec7d763eef3d7ddaa905629b720ee3bee5029805857f3f8b97ddb86c`。
5. 抓取过程未停止、重置或跳过 Unity 游戏时间。

## 未完成项

1. 尚未使用该 Day 3 副本执行广度与深度参数搜索。
2. NPC-NPC 对话样本不足，后续应继续增加 NPC 相遇和完整社交播放样本，或在结果中降低该模式结论置信度。

## 追加抓取：Day 4 当前内容

用户继续运行并增加数据后，于 Day 4 09:38 再次要求抓取当前内容。本次保留 Day 3 副本，新增：

- `docs/AIChanges/artifacts/memory_route_day4_current_source/game_day4_current.db`
- `docs/AIChanges/artifacts/memory_route_day4_current_source/lancedb/`
- `docs/AIChanges/artifacts/memory_route_day4_current_source/manifest.json`

抓取时 Unity 短暂停约 3 秒以固定 SQLite 与 LanceDB 的一致窗口，完成后立即恢复 Play；未改变游戏时间或业务状态。

运行快照：Day 4 09:38、阴天、玩家位于 `player_cafe.kitchen`、无对话、健康状态 `ready`。NPC 中樱正在前往 `player_cafe.doorway` 执行 `give_item`，其余 NPC 正在各自地点执行工作或饮用任务。

| 数据 | Day 3 | Day 4 当前 |
|---|---:|---:|
| 图节点 | 100 | 119 |
| 图边 | 109 | 128 |
| 短期记忆 | 20 | 24 |
| 检索日志 | 191 | 219 |
| 融合来源 | 0 | 6 |
| 玩家对话检索 | 14 | 17 |
| NPC-NPC 对话检索 | 2 | 2 |
| 夜间印象检索 | 175 | 200 |

Day 4 副本 SHA-256：`416708c2a07c81d0e57abaac9caa153cf86cb6867075035a6b6fad489f4b1475`。LanceDB 6 个表均可打开，共 136 行。
