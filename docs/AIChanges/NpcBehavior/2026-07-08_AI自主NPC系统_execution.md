> 设计方案: [2026-07-08_AI自主NPC系统_plan.md](2026-07-08_AI自主NPC系统_plan.md)

# AI 自主 NPC 系统 — 执行记录

## 完成时间
2026-07-08

## 实际改动清单

### 新建文件 (9)

| 文件 | 说明 |
|------|------|
| `backend/src/world/proximity.py` | Zone 邻近判断（are_nearby, get_nearby_npcs, is_same_zone） |
| `backend/src/npc/npc_dialogue.py` | NpcDialogueManager：LLM 对话生成 + 气泡发送 + 占位回退 |
| `Assets/Scripts/NPC/IMovementProvider.cs` | 移动接口 + LerpMovementProvider 默认实现 |
| `Assets/Scripts/NPC/NpcEntity.cs` | NPC 组件（MoveToLocation, PlayAction, ShowBubble） |
| `Assets/Scripts/NPC/NpcSpawner.cs` | NPC 生命周期（OnGameReady 生成, OnNpcBehavior 驱动） |
| `Assets/Scripts/Dialogue/BubbleUI.cs` | 世界空间气泡（淡入淡出, LateUpdate 跟随） |
| `Assets/Scripts/Dialogue/NpcBubbleManager.cs` | 气泡队列路由 + 社交动作处理 |
| `Assets/Scripts/Data/LocationDatabase.cs` | 静态位置查表（GetPositionWithOffset） |
| `Assets/Resources/Config/location_positions.json` | 40 个 location_id 坐标 |

### 修改文件 (5)

| 文件 | 改动 |
|------|------|
| `backend/src/npc/behavior_engine.py` | 完整重写：profile 加载 + P0-P6 链 + 社交检测 + 对话回调 |
| `backend/src/dialogue/prompt_builder.py` | 新增 build_npc_to_npc_prompt() + NPC_DIALOGUE_SYSTEM 模板 |
| `backend/src/main.py` | 导入 NpcDialogueManager + lifespan 初始化 + set_npc_dialogue_callback |
| `Assets/Scripts/Data/MessageTypes.cs` | 新增 NpcBubbleMsg, NpcSocialActionMsg + 路由 + Callbacks |
| `Assets/Scripts/Core/GameManager.cs` | LocationDatabase.Load() + NpcBubble/NpcSocialAction 回调 |

### 更新文件 (2)

| 文件 | 改动 |
|------|------|
| `CLAUDE.md` | 新增 AI 开发规则（行为底线/注释/计划执行文档/低级错误预防） |
| `docs/AIChanges/` | 创建目录 + 首个计划/执行文档对 |

## 遇到的问题

1. **Unity JsonUtility 不支持顶层字典** — location_positions.json 改为数组格式
2. **CS1061 编译错误** — GetPositionWithOffset 返回 Vector2 非 nullable，删除了 `.Value` 调用
3. **prompt_builder.py 自引用导**入 — 将 NPC_DIALOGUE_SYSTEM 模板移到了 prompt_builder.py
4. **chihaya/kazuha/tatsunosuke/kujo 缺少 daily_rhythm** — 回退到 DEFAULT_ROUTINES

## 验证方式

- [x] 后端 import 测试通过
- [x] 后端 `python run.py` 启动成功
- [x] sakura 从 profile 加载 4 条 routines，其余 fallback
- [x] NPC 对话管理器就绪日志确认
- [ ] Unity 编译（需用户在 Editor 内验证）
- [ ] Unity Play 模式 NPC 生成 + 移动 + 气泡

## 未完成项

- Unity NPC 预制体创建（需用户在 Editor 手动操作）
- 场景挂载 NpcSpawner + NpcBubbleManager
- Unity Play 端到端测试
