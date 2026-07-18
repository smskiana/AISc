> 执行记录: [2026-07-08_AI自主NPC系统_execution.md](2026-07-08_AI自主NPC系统_execution.md)

# AI 自主 NPC 系统 — 设计方案

## 需求
跳过 P1 PlayerController，直接构建 NPC 完整自主系统：
- 自主移动（按日程在商店街各地点间移动）
- 自主行为（P0-P6 优先级链：生存/玩家/NPC互访/需求/日常/随机）
- NPC 间相互对话（同 Zone 相遇 → LLM 生成简短对话 → 气泡显示）

## 架构决策

| # | 问题 | 方案 |
|---|------|------|
| 1 | NPC 移动方式 | Lerp + 随机偏移（IMovementProvider 接口，日后可换寻路） |
| 2 | 谁先移动 | 发起方走到目标方 |
| 3 | 对话触发 | 同 Zone + 30min 冷却 + bond 加权概率 |
| 4 | 对话生成 | DeepSeek LLM，2-4 轮，80 tokens/轮 |
| 5 | 位置坐标 | Unity 本地 JSON，后端只用 Zone 名 |

## 涉及文件（预估）

### 新建
- `backend/src/world/proximity.py` — Zone 邻近判断
- `backend/src/npc/npc_dialogue.py` — NPC 对话生成器
- `Assets/Scripts/NPC/IMovementProvider.cs` — 移动接口
- `Assets/Scripts/NPC/NpcEntity.cs` — NPC 实体组件
- `Assets/Scripts/NPC/NpcSpawner.cs` — NPC 生命周期
- `Assets/Scripts/Dialogue/BubbleUI.cs` — 世界空间气泡
- `Assets/Scripts/Dialogue/NpcBubbleManager.cs` — 气泡路由
- `Assets/Scripts/Data/LocationDatabase.cs` — 位置查表
- `Assets/Resources/Config/location_positions.json` — 坐标配置

### 修改
- `backend/src/npc/behavior_engine.py` — 完整重写 P0-P6
- `backend/src/dialogue/prompt_builder.py` — NPC 对话 Prompt
- `backend/src/main.py` — 集成 NpcDialogueManager
- `Assets/Scripts/Data/MessageTypes.cs` — 新消息类型
- `Assets/Scripts/Core/GameManager.cs` — 集成

## 风险点
- Unity 侧无法编译验证，需用户在 Editor 内测试
- NPC 预制体需用户手动创建（[SerializeField] 槽位）
- LLM 对话质量取决于 DeepSeek API 可用性
- location_positions.json 坐标可能与实际场景布局不匹配
