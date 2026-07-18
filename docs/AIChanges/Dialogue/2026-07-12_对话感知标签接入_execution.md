> 设计方案: [2026-07-12_对话感知标签接入_plan.md](2026-07-12_对话感知标签接入_plan.md)

# 对话感知标签接入 — 执行记录

## 完成时间

2026-07-12

## 实际改动清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/src/dialogue/perception_context.py` | 新增 `PerceptionContextBuilder`，统一读取地点、物品、人物配置并生成对话现场感知上下文 |
| `backend/config/player_profile.json` | 新增玩家“小李”的感知档案，约束 NPC 不要假定玩家性别、关系或开店进度 |
| `docs/AIChanges/Dialogue/2026-07-12_对话感知标签接入_plan.md` | 本轮方案 |
| `docs/AIChanges/Dialogue/2026-07-12_对话感知标签接入_execution.md` | 本执行记录 |

### 修改文件

| 文件 | 实际改动 |
|------|------|
| `backend/src/dialogue/prompt_builder.py` | 接入现场感知上下文；玩家对话、NPC 闲聊、玩家快捷回复建议都会注入当前地点 / 人物 / 物品感知；首遇规则收窄，避免诱导“好久不见 / 一点都没变” |
| `backend/config/location_profiles/*.json` | 9 个地点全部补齐 `perception_tags`、`sensory`、`visible_objects`、`conversation_hooks`、`spot_perception`；每个 spot 均有局部感知 |
| `shared/items.json` | 10 个初始物品补齐感知标签、五感描述、存在场景与话题钩子 |
| `backend/config/npc_profiles/*.json` | 5 个 NPC 补齐人物视觉、存在感、说话感与称呼建议 |

## 关键实现说明

### 1. 现场感知成为独立上下文

新增 `PerceptionContextBuilder`，负责把当前对话位置解析成：

1. 地点总览
2. 当前 spot 局部信息
3. 视觉 / 声音 / 气味 / 触感
4. 当前地点自然存在的物品
5. 当前对话人物的视觉、存在感和称呼建议

输出段落统一以 `# 现场感知` 开头。

### 2. 三条对话链路已接入

已接入：

1. 玩家和 NPC 正式对话：`PromptBuilder.build(...)`
2. NPC 和 NPC 闲聊：`PromptBuilder.build_npc_to_npc(...)`
3. 玩家三条快捷回复建议：`PromptBuilder.build_player_reply_suggestions(...)`

Prompt 规则新增：优先根据“现场感知”中当前能看见、听见、闻到的人和物来组织对白。

### 3. 首遇寒暄收窄

原提示中“这是你很久以后第一次见到对方”容易诱导：

```text
好久不见，你一点都没变
```

现改为“开局后第一次正式说话”，并要求：

1. 按记忆判断熟悉程度
2. 如果只是听说对方回来，不要说亲眼确认过的寒暄

### 4. 物品匹配做了收窄

物品只在合适地点出现：

1. 面包只在面包店
2. 和果子只在和果子店
3. 罐装咖啡只在街边贩卖机
4. 河边石头只在公园 / 河边
5. 押花书签只在花店 / 喫茶店

避免 LLM 把未在现场的物品当成“看见了”。

## 验证结果

### Python 编译

已通过：

```powershell
python -m py_compile backend/src/dialogue/perception_context.py backend/src/dialogue/prompt_builder.py
```

### JSON 校验

已通过：

```powershell
python -m json.tool backend/config/player_profile.json
python -m json.tool shared/items.json
python -m json.tool backend/config/location_profiles/*.json
python -m json.tool backend/config/npc_profiles/*.json
```

### 项目规范检查

已通过：

```powershell
python backend/scripts/check_project_conventions.py
```

输出：

```text
规范检查通过：shared ID、profile 主键、location_positions 一致。
```

### Prompt smoke

已用 `PromptBuilder` 本地 smoke 验证：

1. 和叶在旧书店 `bookstore.reading_sofa` 的玩家对话包含 `# 现场感知`
2. 和叶明确为男性，并保留自然称呼建议
3. 旧书店现场包含旧书和猫「煎饼」
4. 旧书店不再误带出煎茶
5. 和叶与九条在 `street.vending_machine` 的 NPC 闲聊包含罐装咖啡
6. 玩家快捷回复建议同样包含现场感知和人物视觉信息

## 未完成项

1. 未启动真实 LLM 观察长时间输出质量。
2. 未做 Unity Play 模式端到端验证。
3. Git 当前显示项目大量文件为未跟踪状态，本轮未做 git stage / commit。
