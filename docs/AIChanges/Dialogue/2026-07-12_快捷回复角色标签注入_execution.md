> 设计方案: [2026-07-12_快捷回复角色标签注入_plan.md](2026-07-12_快捷回复角色标签注入_plan.md)

# 快捷回复角色标签注入 — 执行记录

## 完成时间

2026-07-12

## 实际改动清单

### 修改文件

| 文件 | 实际改动 |
|------|------|
| `backend/src/dialogue/prompt_builder.py` | 玩家快捷回复建议系统规则新增性别/身份边界；建议回复 user prompt 注入当前 NPC 基础信息；新增 `_format_reply_npc_profile()`、`_gender_label()`、`_join_profile_list()` |
| `backend/config/npc_profiles/sakura.json` | 新增 `visual_tags` 与 `address_hint` |
| `backend/config/npc_profiles/chihaya.json` | 新增 `visual_tags` 与 `address_hint` |
| `backend/config/npc_profiles/kazuha.json` | 新增男性视觉标签与禁用“和叶姐/叶姐/姐姐/她”的称呼边界 |
| `backend/config/npc_profiles/tatsunosuke.json` | 新增男性视觉标签与禁用女性称呼边界 |
| `backend/config/npc_profiles/kujo.json` | 新增男性视觉标签与禁用女性称呼边界 |

## 关键实现说明

### 1. 快捷回复现在能看到 NPC 基础档案

`build_player_reply_suggestions(...)` 现在会在 prompt 中加入：

```text
当前 NPC 基础信息：名字=和叶；年龄=22；性别=男性；身份=旧书店「猫之书架」店主；视觉标签=...；玩家称呼边界=...
```

这样生成三条玩家建议时，不再只依赖名字、当前语气和最近对话。

### 2. 规则层明确禁止性别幻觉

系统规则新增：

1. 必须以“当前 NPC 基础信息”为准
2. 不要凭名字、语气或印象猜性别
3. 不要使用与当前 NPC 性别/身份冲突的称呼

目标是压住“和叶姐”“她”“姐姐”等错位称呼。

### 3. Profile 标签只服务提示词，不改主逻辑

新增字段为：

1. `visual_tags`
2. `address_hint`

当前只被快捷回复建议读取，不影响冷启动记忆、NPC 正文对白、行为计划和存档 schema。

## 验证结果

### JSON 校验

已通过：

```powershell
python -m json.tool backend/config/npc_profiles/sakura.json
python -m json.tool backend/config/npc_profiles/chihaya.json
python -m json.tool backend/config/npc_profiles/kazuha.json
python -m json.tool backend/config/npc_profiles/tatsunosuke.json
python -m json.tool backend/config/npc_profiles/kujo.json
```

### Python 编译

已通过：

```powershell
python -m py_compile backend/src/dialogue/prompt_builder.py
```

### Prompt smoke

用 `PromptBuilder.build_player_reply_suggestions("kazuha", ...)` 验证，输出 prompt 已包含：

1. `性别=男性`
2. `视觉标签=男性、22岁、深棕卷发、圆框眼镜...`
3. `不要叫“和叶姐”“叶姐”“姐姐”，不要用“她”`

## 未完成项

1. 未启动真实 LLM 观察三条建议的实际输出质量。
2. 未做 Unity Play 模式端到端验证。
