> 设计方案: [2026-07-10_玩家提示接入向量记忆_plan.md](2026-07-10_玩家提示接入向量记忆_plan.md)

# 玩家提示接入向量记忆 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已将“玩家关于当前 NPC 的向量记忆”接入三条建议回复生成链路。

现在每轮 NPC 回复结束后，后端在生成 `choices` 时会：

1. 先查询玩家向量库里与当前 NPC 相关的记忆
2. 将这些记忆压缩成轻量上下文
3. 再生成 3 条玩家可点击提示

同时仍保留原来的自由输入能力，前端不需要改协议。

## 实际改动清单

### 修改脚本 (2)

- `backend/src/application/dialogue_service.py`
- `backend/src/dialogue/prompt_builder.py`

### 新建文档 (2)

- `docs/AIChanges/Memory/2026-07-10_玩家提示接入向量记忆_plan.md`
- `docs/AIChanges/Memory/2026-07-10_玩家提示接入向量记忆_execution.md`

## 关键实现说明

### 1. 三条提示生成前会查询玩家向量记忆

在 `PlayerDialogueService._build_player_reply_choices(...)` 中新增：

- `_get_player_reply_memories(...)`

逻辑为：

1. 仅当当前对话对象是 `player` 时才查询
2. 优先用 NPC 中文名查玩家记忆
3. 若查不到，再回退用 NPC ID 查一次
4. 最多取 3 条相关记忆

### 2. PromptBuilder 接收玩家记忆并写入建议回复 prompt

`build_player_reply_suggestions(...)` 新增：

- `player_memories`

并在 prompt 中新增一段：

`玩家可能记得的相关往事`

同时加了限制说明：

1. 相关时才自然参考
2. 不相关就不要硬用

这样三条提示会更偏向延续玩家自己的既往话题，而不只是“基于眼前这句临场接话”。

### 3. 玩家记忆做了轻量整理，避免 prompt 过重

新增 `_format_player_reply_memories(...)`：

1. 只取前 3 条
2. 单条过长就截断
3. 多行文本压成单行
4. 没有记忆时明确写成“暂无明显相关记忆”

因此这次接入不会明显冲垮现有 prompt 结构。

## 验证结果

- [x] `dialogue_service.py` 通过 `python -m py_compile`
- [x] `prompt_builder.py` 通过 `python -m py_compile`
- [x] 三条提示生成链路已接入玩家向量记忆查询
- [x] 没有玩家记忆时仍可正常回退

## 未完成项

1. 还没有在实际 Unity 对话中观察“提示内容是否明显更连续、更像玩家自己的话”
2. 还没有评估当前 `search_player_memories()` 的召回质量，后续如果发现偏题，可以再改查询词或加过滤
3. 当前仍然只把玩家记忆用于“三条提示”，还没有用于玩家输入框的自动补全或草稿建议
