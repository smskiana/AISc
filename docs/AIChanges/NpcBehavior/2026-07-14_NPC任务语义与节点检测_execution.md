> 设计方案: [2026-07-14_NPC任务语义与节点检测_plan.md](2026-07-14_NPC任务语义与节点检测_plan.md)

# NPC 任务语义与节点检测执行记录

## 实际改动

1. `shared/actions.json` 移除正式 `walk_to` / `run_to`，新增 `patrol`、`visit`、`sleep`，并建立 action affordance。
2. `shared/locations.json` 为全部 45 个 spot 增加语义标签。
3. 新增后端 `NpcTaskCatalog`，统一校验 action、location、spot tag 和 NPC 限制；LLM 计划只看到已校验候选组合。
4. 新增后端 `NpcTaskTracker`，使用真实单调时间维护阶段询问、progress revision、停滞阈值和较长硬超时。
5. `BehaviorEngine` 不再按 action 名判断移动；任意任务目标不同都会进入 transit，并在 Unity 成功后提交位置和行为记忆。
6. 后端运行时新增独立真实时间监控循环，并接入 `NPC_TASK_STATUS_QUERY / NPC_TASK_STATUS / ACK`。
7. Unity 新增 `NpcTaskExecutor`，统一执行 validating、moving、performing 和前端终态。
8. Unity 支持 `movement_mode=walk/run/none`；run 使用独立速度倍率，不再使用 `run_to` action。
9. 前端保存最近终态快照，状态询问可以恢复丢失的成功、失败或取消结果。
10. 5 名 NPC routine 已迁移为实际任务，规范检查会拒绝移动 action 和非法 action-location 组合。

## 职责减重

- 后端从 `BehaviorEngine` 拆出 `task_catalog.py` 和 `task_tracker.py`。
- 前端 `NpcBehaviorApplier` 退回消息适配，任务状态机进入 `NpcTaskExecutor.cs`。
- `NpcActionResultReporter` 与 `NpcTaskStatusReporter` 分别负责终态和节点快照协议。

## 验证

1. `python backend/scripts/check_project_conventions.py`: 通过，覆盖全部 spot tags、routine affordance 和移动 action 禁止规则。
2. `python -m unittest discover -s backend/tests -v`: 18 项通过。
3. `python -m compileall -q backend/src backend/tests`: 通过。
4. `dotnet build AISc.sln --no-restore`: 通过，0 error；保留既有依赖冲突 / JsonUtility 字段警告。
5. 静态搜索确认运行代码与配置中不存在正式 `walk_to`、`run_to`、`go_home` 引用；仅保留历史说明注释。

## 未完成项

1. 尚未在 Unity Play 模式验证跨店任务、run 速度、长动作状态询问和结果丢包恢复。
2. 当前动作完成仍使用前端等待时长；真实动画 / 交互完成事件尚未接入。
3. 营业状态、精确时间窗和动态 spot 占用尚未进入 affordance。
4. 硬超时当前最多重发一次；替代 spot 和按失败原因重新规划尚未实现。
5. 更细 SceneAnchor / Prefab spot 属于资产层后续工作，必须使用 Unity MCP 单独执行。

## 当前口径文档回写

1. `docs/Roadmap.md`：将导航 / 协议 / 旧前端 Play 回归移入已完成底座，并把 NPC 当前阶段改为新增任务链 Play 与第二阶段 affordance。
2. `docs/Workstreams/NpcBehavior/README.md`：登记任务、移动方式、前端终态和节点检测权威边界。
3. `docs/Workstreams/FrontendArchitecture/README.md`：登记 `NpcTaskExecutor` 与最近终态快照职责。
4. `docs/Workstreams/Navigation/README.md`：明确导航不再识别移动 action，只消费任务的 `movement_mode`。
5. `docs/DesignDocs/CodebaseBigPicture.md`：更新 Core、NPC、Navigation、Dialogue 和完整任务数据流，移除整改前职责描述。
6. `shared/README.md`、代码目录 README 与协议证据入口：补充 affordance、任务 tracker 和协议权威边界。
