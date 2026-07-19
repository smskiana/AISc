# NPC 日程 PlayMode 缺口收口测试记录

> 执行方案：[2026-07-19_NPC日程PlayMode缺口收口_plan.md](2026-07-19_NPC日程PlayMode缺口收口_plan.md)
>
> 实现记录：[2026-07-19_NPC日程PlayMode缺口收口_execution.md](2026-07-19_NPC日程PlayMode缺口收口_execution.md)

## 测试结论

**失败。** 聚焦自动化、六种隔离日程探针、新游戏清理和 day 2 revision 1 接收均通过，但真实跨日链在 5 名 NPC 的 day 2 日程均已接收后，`world_preparation` 仍持续停在 `entering_world`。这直接违反 plan 验收标准 5；必须回到新的执行会话修复，不能认定本案整体完成。

## 测试环境

- 日期：2026-07-19（Asia/Shanghai）
- Unity：2022.3.62t7，WindowsEditor，场景 `Assets/Scenes/Town_Main.scene`
- Unity MCP 实例：`AISc@9db8baa7dcf9cfcd`
- 后端：本机真实运行实例，WebSocket 已连接并完成协议协商
- 测试数据：通过正式 `start_new_game` 清理入口建立的新游戏；真实供应商输出只记录结构化 owner trace，不保存 Prompt 或模型原文

## 工具选择

1. Python 聚焦 pytest：覆盖 planner/parser、required group、fallback 共用校验、物理快照、记忆检查点和新游戏复合清理。
2. Unity EditMode：覆盖日程 controller、replan tracker 和诊断 DTO/隔离 seam。
3. `aisc_control.run_daily_schedule_probe`：可重复触发六种白名单场景，写入范围为 `isolated_in_memory_only`。
4. 真实 Play Mode：通过 `start_new_game` 与 `run_midnight_settlement` 进入正式新游戏和跨日链。
5. `aisc_debug`：读取 `runtime_snapshot`、`daily_schedule_snapshot`、`interaction_replan_snapshot`、`midnight_snapshot`；Console 只作为异常补充。

## 步骤与结构化证据

### 1. Python 聚焦回归

命令：

```text
python -m pytest -q backend/tests/test_daily_schedule_planner.py backend/tests/test_schedule_candidates.py backend/tests/test_schedule_world_snapshot.py backend/tests/test_memory_checkpoint.py backend/tests/test_new_game_backend_purge.py
```

结果：`20 passed in 0.57s`。

首次工具筛选误用了不存在的 `test_schedule_physical_snapshot.py`，pytest 未收集测试；按 `backend/tests/README.md` 和实际文件索引纠正为 `test_schedule_world_snapshot.py` 后通过。该次工具选择错误不计为业务失败。

### 2. Unity EditMode

- 筛选：`NpcDailyScheduleTests`、`AiscDiagnosticsTests`
- 结果：31 passed、0 failed、0 skipped，0.472 秒
- 关键覆盖：single-flight 与匹配终态、超时与跨日取消、revision 内容恒等、日程 probe 稳定裁决、空 operation 不吸附其他 trace。

### 3. 六种隔离日程 probe

全部返回 `success=true` 且写入范围均为 `isolated_in_memory_only`：

| 场景 | 结构化结果 |
|---|---|
| `fixed_input_planner` | `status=success`，6 项，`validation_status=accepted` |
| `provider_timeout` | `status=fallback`，`failure_reason=provider_timeout`，6 项 |
| `jump_to_17` | `decision=Switch`，`reason=schedule_window_active` |
| `social_lock_defer` | `decision=Defer`，`reason=npc_social_dialogue_locked` |
| `task_failure_replan` | `decision=RequestReplan`，`reason=schedule_window_expired` |
| `late_revision` | `decision=rejected`，`reason=stale_schedule_revision` |

### 4. 新游戏与真实 5 NPC planner

正式 `start_new_game` 请求成功；世界准备从 `initial_memory` 收口到 `complete`，`gameplay_ready=true`，5 个 NPC 与 5 份 day 1 / revision 1 / `daily_schedule_v2` 日程均存在。

day 1 真实供应商分布：

- success：3/5（`chihaya`、`kazuha`、`tatsunosuke`）
- fallback：2/5（`sakura`、`kujo`）
- fallback 稳定原因：均为 `schedule_time_conflict`
- 未出现：`AttributeError`、非 object 异常泄漏、结构性 required 超量、仅乱序拒绝

该结果满足验收标准 7 对“已知缺口不得再触发 fallback、其他业务拒绝必须有稳定 failure code”的最低要求，但真实供应商仍有 2/5 业务 fallback，不能当作质量完全收敛。

### 5. 跨日 day 2 revision 1

正式 `run_midnight_settlement` 返回成功；`midnight_snapshot` 为 `status=success`、`phase=complete`，5/5 impression 成功。随后 `daily_schedule_snapshot` 显示 5 名 NPC 均为：

- `schedule_day=2`
- `schedule_revision=1`
- `planner_version=daily_schedule_v2`
- `last_replan_status=idle`

说明 day 2 revision 1 未被 day 1 revision 1 / fingerprint 阻挡，验收标准 4 的计划接收部分通过。

day 2 真实供应商分布为 2/5 success、3/5 fallback；稳定原因包括两个 `schedule_time_conflict` 和一个 `required_group_missing`。未观察到异常类型泄漏。

### 6. 失败证据：world preparation 未收口

在 5 份 day 2 日程均已进入 Unity 后继续观察，`runtime_snapshot.world_preparation` 仍为：

```text
operation_id=world_prepare_f5163a8e9995460599c1e9a7d43264ff
flow=next_day
phase=entering_world
is_active=true
progress_floor=0.85
failure_reason=""
target_game_day=2
```

首次取证时游戏时间为 day 2 08:09；继续等待并再次取证至 day 2 09:36，状态仍未变化。与此同时 `daily_schedule_snapshot` 已显示 5/5 day 2 revision 1，Console error 为 0。按验收标准 5，次日计划终态后 world preparation 不得停在 `entering_world`，因此判定失败。

对应 operation 的 `protocol_trace` 查询为空，Console 中也没有该 operation 的日志，现有证据只能定位到 Unity 世界准备终态收口 seam，不能在测试会话内进一步修改或猜测修复。

## 验收标准裁决

| 标准 | 结果 | 说明 |
|---|---|---|
| 1. 新游戏隔离与同日回放 | 部分通过 | 新游戏生成全新 `daily_schedule_v2` day 1；本轮未重启后端复测同日回放 |
| 2. replan 单飞与终态 | 部分通过 | EditMode 与隔离 probe 通过；未完成真实互动 replan 长链 |
| 3. replan 冻结快照 | 部分通过 | 自动化覆盖通过；真实互动 replan 未触发 |
| 4. day 2 revision 1 原子替换 | 通过（计划接收） | 5/5 均切换为 day 2 revision 1，未见旧 fingerprint 阻挡 |
| 5. world preparation 收口 | **失败** | 5/5 日程已接收后仍持续 `entering_world` |
| 6. planner 解析与统一校验 | 通过 | Python 20/20，稳定 failure code 可见 |
| 7. 真实 5 NPC 已知 fallback 缺口 | 通过最低要求 | 无 `AttributeError`/required 超量/仅乱序；仍有稳定业务 fallback |
| 8. 重复 replan 错误与诊断关联 | 部分通过 | 隔离 probe/DTO 通过；真实 replan 未覆盖 |

## 未覆盖项与后续动作

1. 因验收标准 5 已失败，本测试会话停止扩大范围，未继续执行真实互动 replan、超时/cancel、后端同日重启回放。
2. 新的执行会话应以本 test 的 `world_prepare_f5163a8e9995460599c1e9a7d43264ff` 证据检查 next-day `entering_world -> complete/failed` 终态条件，并补回归测试。
3. 修复后在本文件追加有界复测记录；若修复范围改变主题或系统边界，则另建互链 plan/execution/test。

## 有界复测：NPC 日程世界准备终态修复

> 修复执行记录：[2026-07-19_NPC日程世界准备终态修复_execution.md](2026-07-19_NPC日程世界准备终态修复_execution.md)

### 复测结论

**通过。** 原失败证据保持不变；2026-07-19 的有界复测确认，同一真实 next-day world preparation operation 已从活动态正确收口为 `complete / is_active=false / progress_floor=1 / failure_reason=""`。原验收标准 5 由失败改判为通过。

本次复测只裁决 plan 第 12.5 节的世界准备终态修复；本文件中真实互动 replan、同日后端重启回放等“部分通过”项目仍保持未覆盖，不因本次复测自动通过。

### 环境与工具

- Unity：2022.3.62t7，WindowsEditor，`Assets/Scenes/Town_Main.scene`
- Unity MCP 实例：`AISc@9db8baa7dcf9cfcd`
- 后端：本机真实运行实例，WebSocket 已连接且协议协商完成
- 工具：Unity EditMode Test Runner、`aisc_control.start_new_game`、`aisc_control.run_midnight_settlement`、`aisc_debug.runtime_snapshot`、`daily_schedule_snapshot`、`midnight_snapshot`、Console
- 未运行 Python 测试：本次修复仅改变 Unity 纯 C# tracker、协议适配和既有 DTO 字段投影，Python/planner 行为未修改

### 聚焦状态机复测

- 筛选：`WorldPreparationStateTrackerTests`
- 结果：7 passed、0 failed、0 skipped，0.348 秒
- 覆盖：活动 operation 建立、匹配成功、匹配失败并保留进度、其他 operation 进度拒绝、迟到 complete/failed 拒绝、终态后迟到 progress 不复活。

因此 plan 第 12.5.4 与 12.5.5 的稳定失败和迟到 operation 要求由可控纯 C# seam 覆盖，不为制造失败污染正式存档或后端数据。

### 真实 Play Mode 跨日证据

1. 正式新游戏完成：`world_prepare_0176fb81d1dc4280941421ac8c6931a1` 收口为 `initial_world / complete / is_active=false / progress_floor=1`，5 个 NPC 已建立，`gameplay_ready=true`。
2. 正式午夜入口建立 next-day operation：

```text
operation_id=world_prepare_1217dcbcb6db476784cd632016d9232e
flow=next_day
phase=memory_settlement
is_active=true
failure_reason=""
target_game_day=2
```

3. 同一 operation 最终状态：

```text
operation_id=world_prepare_1217dcbcb6db476784cd632016d9232e
flow=next_day
phase=complete
is_active=false
progress_floor=1
failure_reason=""
target_game_day=2
```

4. 同步业务证据：
   - `midnight_snapshot`：`status=success`、`phase=complete`、5/5 impression 成功、无 failure reason。
   - `daily_schedule_snapshot`：5/5 NPC 均为 `schedule_day=2`、`schedule_revision=1`、`planner_version=daily_schedule_v2`。
   - `runtime_snapshot`：`gameplay_ready=true`，暂停来源为空，`save.phase=Idle`，玩家位于 `player_cafe.bed`，说明加载遮罩、SleepController 次日推进和自动存档链未卡住。
   - Console：0 error。

### 复测裁决

| 复测项 | 结果 |
|---|---|
| 匹配成功终包收口 | 通过 |
| 匹配失败终包稳定失败 | 通过（EditMode seam） |
| 旧 operation 迟到 complete/failed 隔离 | 通过（EditMode seam） |
| 终态后迟到 progress 不复活 | 通过（EditMode seam） |
| 真实 next-day 同 operation `entering/activity -> complete` | 通过 |
| midnight、5 份目标日日程、gameplay ready 联合证据 | 通过 |
| Console 与加载/睡眠/存档冒烟 | 通过 |

原验收标准 5 的修复已完成并通过独立复测；原测试记录其余未覆盖项维持原裁决。

## 有界复测：NPC 日程冻结快照 revision 污染修复

> 修复执行记录：[2026-07-19_NPC日程冻结快照revision污染修复_execution.md](2026-07-19_NPC日程冻结快照revision污染修复_execution.md)
>
> 第 13.5.5 条后续修复记录：[2026-07-19_NPC日程过期replacement修复_execution.md](2026-07-19_NPC日程过期replacement修复_execution.md)；本节当前失败结论保留，等待独立复测追加裁决。

### 复测结论

**部分通过，完整验收失败。** 请求组装修复已通过自动化和真实协议行为验证：当前世界 revision 与冻结引用 revision 不同时，replan 仍通过后端三元组精确校验并进入 planner，不再出现 `schedule_snapshot_version_mismatch`。但 plan 第 13.5.5 条失败：成功 replan 返回的新计划重新包含已经错过的旧 required 步骤，下一分钟再次触发 replan，形成不依赖 version mismatch 的新循环。

本测试会话不修改运行代码。后续应进入新的执行会话修复“成功 replan 未裁剪过期步骤”；修复后在本节追加有界复测。

### 环境与工具

- Unity：2022.3.62t7，WindowsEditor，`Assets/Scenes/Town_Main.scene`
- Unity MCP 实例：`AISc@9db8baa7dcf9cfcd`
- 后端：本机 `backend/run.py` 真实进程，WebSocket 已连接并完成协议协商
- 数据：通过正式 `aisc_control.start_new_game` 建立的 day 1 新游戏
- 工具：Unity EditMode Test Runner、`aisc_control.start_new_game`、`aisc_debug.runtime_snapshot`、`daily_schedule_snapshot`、`interaction_replan_snapshot`、`protocol_trace`、只读 Unity 运行时取证和 Console
- 未运行 Python 测试：本次实现未修改后端；后端 `ScheduleWorldSnapshotStore.require` 的精确拒绝逻辑作为既有契约参与真实链验证

### EditMode 证据

首次按单测名筛选只返回程序集节点 `AISc`，结果为 0 个叶子测试；检查发现新增 `GameCommandSenderTests.cs` 尚未生成 `.meta`，因此执行记录中的测试任务成功不能证明该用例实际被发现。执行 Unity 强制资产刷新和编译后，`.meta` 正常生成，Console 编译 error 为 0。

刷新后运行完整 EditMode 套件：

- 结果：50 passed、0 failed、0 skipped，1.242 秒
- 关键用例：`GameCommandSenderTests.BuildNpcScheduleReplanRequestCommand_UsesFrozenSnapshotRevision` 明确被发现并通过
- 同步回归：`NpcDailyScheduleTests.ReplanTracker_EnforcesSingleFlightAndMatchingTerminal` 等单飞、终态和日程用例均通过

### 真实 PlayMode 与协议证据

1. 正式新游戏完成，`world_prepare_0658cbbb11474756a8ef31a9efa17b54` 收口为 `complete / is_active=false / progress_floor=1`，5 个 NPC 和 day 1 revision 1 日程就绪，连接全程保持 negotiated。
2. 只读运行时取证显示：

```text
current_world_revision=2
snapshot_id=world_1_8_0_87cd0fbf58e14d59aaf6c280ab4ebec7
snapshot_time_revision=0
snapshot_world_revision=0
snapshot_game_day=1
```

当前 `WorldRevision=2` 已与冻结引用 `world_revision=0` 明确分离，满足复现旧污染条件。
3. 窗口错过后正式 runtime seam 触发 replan。`sakura` 的 operation `schedule_replan:sakura:1:1:d458da682ccf4fa0bb27d7244dc06417` 通过后端校验并产生 planner owner trace，Unity 日程由 revision 1 替换为 revision 2；`chihaya` 等 NPC 也随后进入 revision 2。若请求仍携带当前 revision 2，后端会在 planner 前返回 `schedule_snapshot_version_mismatch`，不可能产生这些 owner trace 和替换终态。
4. Console 中 `schedule_snapshot_version_mismatch` 为 0，Console error 为 0。`protocol_trace` 当前只记录带 `request_id` 的 envelope 元数据，不投影 replan payload 三字段，因此无法从该诊断直接抄录出站 JSON；本次以冻结引用只读值、后端精确校验后的 owner trace和 Unity revision 替换构成联合协议证据。
5. 请求处理中每名 NPC 保持单一 pending operation；额外分钟 Tick 记录 `replan_already_in_flight`，没有为同一 base revision 生成第二个 operation ID，单飞语义通过。

### 失败证据：成功 replan 重新引入过期步骤

`sakura` 首次 replan 成功后并未稳定退出恢复链。后续结构化快照显示：

```text
schedule_revision=4
last_operation_id=schedule_replan:sakura:1:3:14db99e3fd2c47219974034b29945684
last_replan_operation_id=schedule_replan:sakura:1:4:2f606c5f6f0a4d91aba79cb06c2df59d
last_replan_status=pending
pending_candidate_id=91257619009c6ca0
last_decision_reason=schedule_window_expired
```

revision 4 的 replacement payload 仍包含原 day 1 `08:00 work_open`：

```text
91257619009c6ca0:work_open:flower_shop.doorway:08:00
```

当时游戏时间已经晚于该窗口，最近完成的 revision 3 operation 甚至为 `status=success / validation_status=accepted`。因此不是稳定失败保留旧日程，而是成功 replacement 本身重新引入过期 required 项，随后立刻为同一 candidate 创建 revision 4 pending。`sakura` 从 revision 1 连续增长到 revision 4，证明原 version mismatch 循环已消失，但被新的“成功替换仍不可执行”循环取代。

### 复测裁决

| Plan 13.5 验收项 | 结果 | 证据 |
|---|---|---|
| 1. 冻结引用完整投影 | 通过 | EditMode 关键用例被正式发现并通过；完整套件 50/50 |
| 2. 正式窗口错过触发 | 通过 | 多名 NPC 通过 runtime seam 产生真实 replan operation |
| 3. 后端接受且无 version mismatch | 通过 | planner owner trace、revision 替换；mismatch Console 0 条 |
| 4. 同 base revision 单飞 | 通过 | 每名 NPC 单一 pending；额外 Tick 仅返回 `replan_already_in_flight` |
| 5. 终态释放且不再循环 | **失败** | 成功 replacement 重含 `08:00 work_open`，revision 1 连续增长到 4并再次 pending |
| 6. 诊断关联与稳定连接 | 部分通过 | owner trace 与 Unity operation 可关联、连接稳定、Console 0 error；`protocol_trace` 不暴露 payload 三字段 |

### 后续动作

1. 新执行会话应先定位 replan planner/fallback 最终校验为何允许 `planned_start_time < 当前 replan game_time` 的候选进入 replacement，并确认 required group 对“已错过必选项”的退役或替代语义。
2. 不得回退本次冻结三元组修复、放宽后端 snapshot 校验或削弱单飞；这些部分已经通过。
3. 修复应保证成功 replacement 不包含在当前 replan 时间已经不可执行的步骤，或以明确领域语义终态化该 required 项；不能只增加静默 retry/backoff 掩盖成功结果不可执行。
4. 修复后复测至少证明同一原始错过 candidate 在成功 replacement 后不再出现、schedule revision 稳定、pending 释放，并保持 `schedule_snapshot_version_mismatch=0`。

### 追加复测：过期 replacement 时间下界修复

> 执行记录：[2026-07-19_NPC日程过期replacement修复_execution.md](2026-07-19_NPC日程过期replacement修复_execution.md)

#### 复测结论

**失败。** 新增的 operation 冻结时间下界在 Python 聚焦测试中生效，也能把 provider 的过期输出稳定收口为 `schedule_start_before_operation` 并使用 fallback；但真实 PlayMode 中 planner 的 8-9 秒耗时期间游戏时间继续推进，按请求时刻排出的 fallback 在到达 Unity 时已经再次过期。原错过的 `work_open` candidate 没有退役，只被改排到请求时刻，导致 revision 和 pending 循环继续增长。

本测试会话未修改实现。后续必须返回新的执行会话；不能把本轮自动化通过当作真实链通过。

#### 环境与门禁

- Unity：2022.3.62t7，WindowsEditor，`Assets/Scenes/Town_Main.scene`
- 后端：本测试会话通过正式 `backend/run.py` 启动的新进程，健康检查 `/api/health` 通过，确保加载 2026-07-19 13:54 后的新实现；测试后已停止
- Unity 连接：新 session `session_f1cb4df866b14c89a579d7fb78f5e25b`，全程 connected / negotiated
- 测试数据：正式 `aisc_control.start_new_game` 建立的干净 day 1
- Python 聚焦测试：`python -m pytest -q backend/tests/test_daily_schedule_planner.py`，9 passed、0 failed，0.17 秒
- Unity Console：error 0 条；`schedule_snapshot_version_mismatch` 0 条

#### 正式链证据

1. 新游戏 operation `world_prepare_ea48ad45e6ba4f8baa9edb6498f4b363` 收口为 `complete / is_active=false / progress_floor=1`，5 个 NPC 与 revision 1 日程就绪。
2. `sakura` 首轮 runtime recovery replan `schedule_replan:sakura:1:1:3a3d1fca441c429c902e13986d8cc69b` 进入后端 planner。provider 结果因早于请求时刻被拒绝：

```text
status=fallback
failure_reason=schedule_start_before_operation
elapsed_sec=8.936082
```

3. fallback 以冻结请求时间约 13:31 为下界生成 revision 2：

```text
91257619009c6ca0:work_open:flower_shop.doorway:13:31
77db5652ca90aae1:eat:flower_shop.back_room:13:32
...
```

但取证时 Unity 当前时间已经是 day 1 16:44；replacement 最早步骤在应用时已经落后 193 个游戏分钟。`last_replan_status=pending`，下一 operation 已为 `schedule_replan:sakura:1:2:b0d48d5ffc374e3492532fdfe019703b`。
4. 继续观察一轮后，循环没有收敛：

```text
current_game_time=day 1 22:11
schedule_revision=4
last_operation_id=schedule_replan:sakura:1:3:f20b789a5f9b47ec96e4b2b88d62bab8
last_replan_operation_id=schedule_replan:sakura:1:4:94d54b98a9e945fb897505aceabdfeab
last_replan_status=pending
pending_candidate_id=91257619009c6ca0
last_decision_reason=schedule_window_expired
```

revision 4 的最早步骤仍为同一 candidate，时间仅推进到 18:05：

```text
91257619009c6ca0:work_open:flower_shop.doorway:18:05
```

最近完成的 revision 3 operation 同样为 `fallback / schedule_start_before_operation`，耗时 9.4258585 秒。到 22:11 时，18:05 又已过期 246 个游戏分钟，随即创建 revision 4 pending。
5. `chihaya` 同样在 revision 2 replacement 中把 `work_open` 调整为 13:31，而当前时间已到 16:44，并创建 revision 2 pending；问题不是单个 NPC 数据异常。

#### 裁决

| 复测项 | 结果 | 说明 |
|---|---|---|
| Python 对 provider 过期时间的拒绝 | 通过 | 9/9；真实 owner trace 为 `schedule_start_before_operation` |
| fallback 不早于请求冻结时间 | 通过 | 首轮从 13:31 严格递增排程 |
| replacement 到达时仍可执行 | **失败** | 到达 Unity 时已经 16:44 |
| 原错过 candidate 退役 | **失败** | `91257619009c6ca0 work_open` 持续出现在 revision 2-4 |
| revision 稳定、pending 释放 | **失败** | revision 1 增至 4，revision 4 仍 pending |
| 冻结三元组与单飞无回归 | 通过 | mismatch 0 条；每个 base revision 仍只有单一 pending |

#### 后续修复边界

1. 新执行会话必须显式处理“operation 冻结时间到结果应用时间之间，Unity 游戏时间继续推进”的时序，不能继续把请求时下界等同于应用时可执行下界。
2. 需要确认运行时恢复 replacement 对已错过 required candidate 的正式语义：退役、选择仍可执行的同组替代项，或在应用前由 Unity 按当前权威时间拒绝过期 replacement。不得只是把同一 candidate 顺延到已经过去的请求时刻。
3. 若采用后端生成余量，余量必须来自明确的游戏时间/协议契约，不能用真实秒数猜测供应商耗时；若采用 Unity 应用时复核，迟到结果必须有稳定终态，不能清 pending 后立即重发同一不可执行内容。
4. 冻结 snapshot 三元组、后端精确校验和 `NpcScheduleReplanTracker` 单飞已经通过，后续不得放宽或移除。
