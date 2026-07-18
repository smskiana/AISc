# Prompt 迁移丢失发言主体契约

## 现象

玩家快捷回复在迁入 `PromptAssembler` 后仍能返回格式正确的 `{"choices": [...]}`，但真实 LLM 会生成 NPC 自述、NPC 口吻或括号动作，使按钮不再是玩家可直接发送的台词。

## 根因

旧业务常量中有“站在玩家口吻、不要替 NPC 说话”的规则，但正式 `player_reply_suggestions` contract 未迁入该约束；调用方的 `target_name` 实际是玩家名，YAML 却把它渲染为当前 NPC。NPC 对玩家的关系和 NPC 语气也没有明确方向，容易被模型误当成玩家人格指令。

## 为什么既有格式测试未捕获

JSON、条数、去重和长度都可以正确，却无法判断台词属于谁。只测 YAML 是否可加载或 context 是否含字段，也无法发现最终渲染文本把双方身份标错。

## 正确做法

1. 用语义明确的 `player_name` 和 `npc_name`，不复用含义模糊的 `target_name`。
2. 在 task system contract 明确发言者、接收者、纯台词规则，以及关系/语气/感知只作背景的方向；机器 JSON contract 只管格式。
3. 从公开 `PromptBuilder.build_player_reply_suggestions()` seam 断言最终 messages，而不是只断言 context 字典。
4. 解析层仅拦确定性违规：当前 NPC 显示名加冒号、开头成对括号动作；复杂中文语义不要堆进 `PlayerDialogueService`。
5. 同步有界 trace，记录期望主体、上下文键、数量、裁剪预览、拒绝原因和 fallback，绝不保存完整 Prompt 或原始 LLM 输出。

## 适用检查清单

迁移任何 Prompt 时，逐项核对：任务发言者、接收者、每个上下文字段的拥有者和方向、最终 response contract、公开 seam 回归测试，以及诊断是否能证明实际运行的主体契约。
