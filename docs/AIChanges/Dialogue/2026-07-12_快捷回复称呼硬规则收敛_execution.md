> 设计方案: [2026-07-12_快捷回复称呼硬规则收敛_plan.md](2026-07-12_快捷回复称呼硬规则收敛_plan.md)

# 快捷回复称呼硬规则收敛 — 执行记录

## 完成时间

2026-07-12

## 实际改动清单

| 文件 | 实际改动 |
|------|------|
| `backend/src/dialogue/prompt_builder.py` | 快捷回复系统规则移除“不要叫姐 / 不要用她”类硬禁令，改为参考现场感知和人物信息自然称呼；快捷回复基础信息里的“玩家称呼边界”改为“称呼建议” |
| `backend/src/dialogue/perception_context.py` | 人物感知输出中的“称呼边界”改为“称呼建议” |
| `backend/config/npc_profiles/*.json` | 5 个 NPC 的 `address_hint` 改为正向称呼建议，不再写硬性禁令 |
| `backend/config/player_profile.json` | 玩家称呼提示改为自然称呼与关系以实际对话/记忆为准 |
| `docs/AIChanges/Dialogue/2026-07-12_对话感知标签接入_execution.md` | 同步更新旧记录中的“称呼边界 / 不要叫”表述 |
| `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-12.md` | 同步改为“称呼建议” |

## 关键说明

本轮没有移除现场感知层。

保留：

1. 人物 `visual_tags`
2. 人物 `presence_tags`
3. 人物 `speech_perception`
4. 现场感知里的性别、身份、存在感

移除 / 收敛：

1. 快捷回复系统 prompt 中的硬性性别称呼禁令
2. profile 中“不要叫某某 / 不要用某代词”的硬文本

现在模型仍能看到“和叶：男性、文艺青年、旧书店店主”，但不会在 prompt 里看到贴脸的禁止句。

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
python -m json.tool backend/config/npc_profiles/*.json
```

### 项目规范检查

已通过：

```powershell
python backend/scripts/check_project_conventions.py
```

### Prompt smoke

用和叶快捷回复建议 smoke 验证：

```text
has_perception True
has_male True
has_address_suggestion True
has_hard_ban False
```

同时 `rg` 未在后端配置 / prompt / 本轮主要交接文档中找到：

```text
不要叫
不要用
性别/身份冲突
称呼边界
玩家称呼边界
和叶姐
```

## 未完成项

未启动真实 LLM 和 Unity Play 模式长测。
