> 设计方案: [2026-07-09_后端应用层重构_plan.md](2026-07-09_后端应用层重构_plan.md)

# 后端应用层重构 — 执行记录

## 完成时间
2026-07-09

## 重构目标达成情况

本次重构已经完成以下目标：

1. `main.py` 从“巨型业务入口”收缩为“薄传输入口”
2. 后端运行时状态集中到 `GameRuntime`
3. 玩家对话会话从入口模块拆分为独立服务
4. WebSocket / HTTP 轮询桥接消息抽离为消息总线
5. `PromptBuilder` 不再通过 `sys.modules` 反向偷读 `main`
6. 存档恢复后可重建向量层相关服务，避免运行时持有旧句柄

## 新建文件 (5)

| 文件 | 作用 |
|------|------|
| `backend/src/application/__init__.py` | 应用层包入口 |
| `backend/src/application/services.py` | `AppServices` 运行时服务容器 |
| `backend/src/application/message_bus.py` | 统一管理活动连接与轮询消息队列 |
| `backend/src/application/dialogue_service.py` | 玩家↔NPC 对话会话服务 |
| `backend/src/application/runtime.py` | 后端运行时编排器 `GameRuntime` |

## 修改文件 (5)

| 文件 | 实际改动 |
|------|------|
| `backend/src/main.py` | 重写为薄入口：只保留 FastAPI 生命周期、REST 路由、WebSocket 路由，并委托给 `GameRuntime` |
| `backend/src/dialogue/prompt_builder.py` | 新增 `set_plan_provider()`；移除通过 `sys.modules.get("src.main")` 读取 `behavior` 的逻辑 |
| `backend/src/npc/behavior_engine.py` | 新增 `get_remaining_plan_summary()` 作为公开只读计划摘要接口 |
| `backend/src/save/manager.py` | 存档时额外备份 `lancedb/`；加载时恢复向量目录 |
| `backend/src/application/runtime.py` | 存档恢复后重建向量层相关服务，保持运行时对象和磁盘状态一致 |

## 关键重构说明

### 1. `main.py` 退回薄入口

原本 `main.py` 同时承载：
- 生命周期初始化
- 服务实例
- 午夜流程
- 对话会话
- 消息队列
- REST/WS 桥接

现在这些逻辑已拆分：
- 运行时编排 → `GameRuntime`
- 对话会话 → `PlayerDialogueService`
- 广播/轮询桥接 → `MessageBus`

`main.py` 只负责：
- 创建 `FastAPI app`
- 定义 endpoint
- 把请求委托给 `runtime`

### 2. 运行时状态统一收敛

使用 `AppServices` 收纳：
- sqlite
- vector store
- state manager
- prompt builder
- memory manager
- retrieval
- evolution
- save manager
- behavior engine
- npc dialogue manager

这样后续如果继续加：
- 强制回忆
- 玩家选项生成
- 调试后台
- 多客户端观察端

不再需要回到 `main.py` 堆全局变量。

### 3. 对话会话正式独立

`PlayerDialogueService` 负责：
- `start_dialogue`
- `handle_player_choice`
- `end_dialogue`
- 玩家记忆提取
- 玩家记忆搜索

好处：
- 会话状态不再散在入口模块
- 后续加“对话中断恢复/多轮状态机”时有稳定落点

### 4. `PromptBuilder` 与 `BehaviorEngine` 的耦合改为显式注入

旧方式：
- `PromptBuilder` 直接读 `main` 模块全局 `behavior`
- 依赖隐藏、调试困难、容易随入口结构变化而坏

新方式：
- `BehaviorEngine` 提供 `get_remaining_plan_summary()`
- `GameRuntime` 初始化时注入给 `PromptBuilder`

这使得依赖方向变成：

`runtime -> behavior -> prompt_builder`

而不再是：

`prompt_builder -> sys.modules -> main.behavior`

### 5. 向量层存档一致性补齐

顺手修复了一个架构层很重要的问题：
- 以前存档只备份 SQLite
- 向量层 `lancedb/` 不参与保存与恢复
- 这会导致读档后“图层/数据层”不一致

现在：
- `SaveManager.save()` 会备份 `data/lancedb`
- `SaveManager.load()` 会恢复该目录
- `GameRuntime` 在 LOAD 后会重建向量层相关服务，避免运行时继续持有旧句柄

## 验证结果

### 已完成验证

- [x] Python 语法编译通过：
  - `backend/src/main.py`
  - `backend/src/application/services.py`
  - `backend/src/application/message_bus.py`
  - `backend/src/application/dialogue_service.py`
  - `backend/src/application/runtime.py`
  - `backend/src/dialogue/prompt_builder.py`
  - `backend/src/npc/behavior_engine.py`
  - `backend/src/save/manager.py`

- [x] 启动入口导入检查通过：
  - 按 `backend/run.py` 的导入方式执行 `import src.main`
  - 返回 `import-ok`

### 尚未做的联调验证

- [ ] 实际启动 `python backend/run.py`
- [ ] Unity 连接后 `GAME_START`
- [ ] 玩家点击 NPC 开始对话
- [ ] NPC 自主社交气泡链路
- [ ] 存档 / 读档后记忆向量一致性

## 未改动但仍值得后续关注

1. `BehaviorEngine` 仍然偏大，虽然入口层已收薄，但它本身未来仍可继续拆为：
   - planning
   - social
   - tick orchestration
2. `PromptBuilder` 仍然较重，后续可拆：
   - 玩家对话 prompt
   - NPC↔NPC prompt
   - 文本标签/地点标签映射
3. Unity 目前仍是 HTTP 桥接 + 轮询模式，不是真正的原生 WebSocket

## 结论

这次不是简单“修 bug”，而是把后端从“单文件粘合架构”推进到了“有明确应用层的可持续架构”：

- 入口变薄了
- 依赖方向变清楚了
- 运行时状态集中管理了
- 对话与广播从入口里拿出来了
- 存档恢复和向量层一致性也比之前更完整
