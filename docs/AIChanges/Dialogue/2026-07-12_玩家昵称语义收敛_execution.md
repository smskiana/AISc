> 设计方案: [2026-07-12_玩家昵称语义收敛_plan.md](2026-07-12_玩家昵称语义收敛_plan.md)

# 玩家昵称语义收敛 — 执行记录

## 实际改动

1. 新增 `backend/src/dialogue/player_name.py`
   - 统一读取 `backend/config/player_profile.json`。
   - 提供玩家语义名、昵称、`玩家（昵称：xxx）` 标签。
   - 提供 `render_player_tokens()`，在 prompt 拼接前替换 `{player_nickname}`、`{player_name}`、`{player_label}`。
   - 当昵称不是默认“小李”时，会把进入 prompt 的旧默认昵称替换为当前昵称，兼容旧图记忆和旧短期文本。

2. 更新玩家配置
   - `backend/config/player_profile.json` 保留 `"name": "玩家"` 与 `"nickname": "小李"`。
   - `address_hint` 改为使用 `{player_nickname}` 占位符。

3. 接入对话 prompt
   - `PromptBuilder._get_target_name("player")` 改为读取玩家昵称。
   - 玩家-NPC system prompt、NPC-NPC prompt、快捷回复 user prompt 返回前统一渲染昵称。
   - 玩家走到 NPC 面前的首句叙述改为“玩家走到了你面前”，避免把昵称生硬嵌入动作旁白。

4. 接入现场感知
   - 玩家人物行显示为 `玩家（昵称：小李）`。
   - 玩家 profile 里的称呼建议和说话感会在输出前渲染占位符。

5. 接入记忆与检索
   - 冷启动共享记忆改为 `{player_nickname}` 占位符，写入图前渲染。
   - LanceDB 节点值、夜间印象 prompt、近期目标记忆片段在输出前渲染昵称。
   - 检索玩家关键词从固定“小李”改为当前昵称 + 玩家 + 旧默认昵称 + 玩家背景关键词，兼容未来改昵称后的旧数据。

6. 接入 NPC 闲聊与行为 prompt
   - NPC 闲聊事实守卫改为动态玩家别名正则。
   - 事实守卫兜底句改为 `{player_nickname}` 模板。
   - 行为日计划、社交判断、社交后重规划 prompt 在发给 LLM 前渲染昵称。

## 验证方式

1. Python 编译通过：
   - `python -m py_compile backend/src/dialogue/player_name.py backend/src/dialogue/perception_context.py backend/src/dialogue/prompt_builder.py backend/src/application/dialogue_service.py backend/src/npc/state_manager.py backend/src/memory/retrieval.py backend/src/npc/npc_dialogue.py backend/src/npc/behavior_engine.py`

2. JSON 校验通过：
   - `python -m json.tool backend/config/player_profile.json`

3. 项目规范检查通过：
   - `python backend/scripts/check_project_conventions.py`

4. Prompt 渲染 smoke 通过：
   - 默认配置输出 `玩家（昵称：小李）`。
   - 临时 monkeypatch 昵称为“小遥”后，`{player_nickname}`、`{player_label}` 与旧默认“小李”均在 prompt 前渲染为“小遥”。

## 未完成项

1. 未启动真实 LLM 长测；本轮只验证 prompt 拼接和静态检查。
2. 旧数据库里已经持久化的昵称文本不会被迁移，只会在进入 prompt 的输出阶段做兼容替换。
