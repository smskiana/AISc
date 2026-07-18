# 工作流：协议与存档

## 当前目标

建立 Unity 权威世界存档、Python 权威记忆检查点，以及支持版本、幂等、重连和一致性提交的双端协议底座。

## 当前工程口径

1. Unity 是玩家、世界、NPC 玩法事实和未来经营数据的存档权威。
2. Python 只权威保存 AI 记忆、记忆关系和向量索引。
3. 两端不共用数据库，通过 `checkpoint_id` 形成一致逻辑存档。
4. Python 中现有世界状态表处于兼容迁移期，不能反向覆盖 Unity 权威快照。
5. 运行时临时状态不进入长期存档，读档后取消并重建。
6. 新协议以 envelope 为目标，迁移期间兼容旧扁平 JSON。
7. `GAME_READY` 与 `MIDNIGHT_SETTLEMENT_COMPLETE` 是世界可操作的成功终态；`WORLD_PREPARATION_PROGRESS` 只反馈阶段体验，不能据此解除 Unity Gameplay 锁。

## 实施阶段

1. 设计与 ADR：已定稿。
2. 协议公共层与握手：已完成。
3. Python 记忆检查点原子化：已完成。
4. Unity 主存档框架：已完成。
5. 双端保存 / 读档事务：已完成。
6. 重连与世界快照：已完成。
7. 旧后端世界状态迁移：已完成持久化权威迁移；运行时缓存保留。
8. 协议与存档底座 Play 回归：已由用户完成并确认。

## 当前验证状态

1. Python 协议、记忆检查点、NPC 社交和既有行为测试共 31 项通过。
2. Unity MCP 编译通过，Console 0 error。
3. Unity EditMode 测试框架可运行，但当前项目没有实际 EditMode 用例。
4. 用户已确认真实双进程保存、覆盖保存、加载、失败恢复与断线重连的 Play 回归完成。

当前状态：协议与存档底座不再属于待验证事项。后续新增玩法只需按现有状态所有权、envelope 和 checkpoint 契约接入，不重新打开底座设计或既有 Play 回归。

开发期临时策略：每次确认进入新游戏时，Unity 通过 `memory_checkpoints_purge_all` 永久清除 Python 全部记忆检查点，收到成功响应后再清除 Unity 全部主存档；清理失败不得进入新游戏。该策略不改变 Unity 世界权威、Python 记忆权威的边界。

## NPC 社交协议

NPC-NPC 对话已复用请求关联和终态权威原则：Python 的 decision 只返回语义意愿；Unity 原子持有 reservation、会合、内容等待、播放、超时和终态。双方会合后 Unity 才发送 `NPC_SOCIAL_CONTENT_REQUEST`，Python 返回结构化 `NPC_SOCIAL_CONTENT_RESULT`；只有匹配参与者且 revision 不陈旧的 COMPLETE 才提交记忆。后端不再发送 PREPARE/CANCEL，也不监督会合超时。

## 代码入口

- Unity 连接：`Assets/Scripts/Core/WebSocketClient.cs`
- Unity 命令：`Assets/Scripts/Core/GameCommandSender.cs`
- Unity 协议：`Assets/Scripts/Protocol/`
- Unity 存档：`Assets/Scripts/Save/`
- Python 应用路由：`backend/src/application/runtime.py`
- Python 协议：`backend/src/protocol/`
- Python 记忆检查点：`backend/src/save/`

## 设计与决策

1. `docs/DecisionRecords/ADR-0006-unity-authoritative-save-memory-checkpoint.md`
2. `docs/DesignDocs/ProtocolAndSaveFoundation.md`

## 执行证据

详见 `docs/AIChanges/ProtocolAndIntegration/README.md`。
