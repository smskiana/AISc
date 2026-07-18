> 设计方案: [2026-07-17_玩家快捷回复主体契约修复_plan.md](2026-07-17_玩家快捷回复主体契约修复_plan.md)

# 玩家快捷回复主体契约修复执行记录

## 状态

- Status: Completed
- 日期: 2026-07-17
- 主要功能域: 对话系统

## 实际改动

1. `PromptBuilder.build_player_reply_suggestions()` 删除未使用的旧 `user_prompt` 和无引用兼容常量；正式 context 改为独立 `player_name`、`npc_name`、`relationship_from_npc`、`npc_speech_hint` 等结构化事实。
2. `player_reply_suggestions` system contract 明确玩家为唯一发言者、当前 NPC 为接收者，且 NPC profile/关系/语气/现场感知只作背景；JSON response contract 保持仅负责机器格式。
3. `PlayerDialogueService` 增加最小确定性收口：拒绝当前 NPC 显示名加冒号和开头成对括号动作，随后复用 `_merge_with_fallback_choices()` 补足三条；未引入中文语义分类器。
4. 新增 `ReplySuggestionTraceStore`，以固定容量保存裁剪选择预览、拒绝原因、主体预期、context 键、fallback、失败原因与耗时；`GET /api/dialogue/player_reply_suggestion_snapshot` 和 Unity `aisc_debug.player_reply_suggestion_snapshot` 仅作只读代理。
5. 增加后端 Prompt/解析/trace 回归测试、Unity DTO EditMode 测试，并更新 Prompt、Dialogue、Diagnostics、Workstream 与错误预防入口文档。

## 验证

- 后端针对性测试：`python -m pytest backend/tests/test_prompt_assembler.py backend/tests/test_prompt_registry.py backend/tests/test_dialogue_reply_suggestions.py backend/tests/test_reply_suggestion_diagnostics.py -q`，10 passed。
- 后端全量测试：先顺序运行 `python -m py_compile` 覆盖 4 个变更 Python 模块，再运行 `python -m pytest backend/tests -q`，87 passed、3 subtests passed。
- Unity：4 个变更脚本脚本级校验均为 0 error / 0 warning；`AiscDiagnosticsTests` EditMode 11 passed。
- Play Mode：通过既有 `aisc_control` 的 `start_new_game`、`start_dialogue`、`send_player_choice`、`end_dialogue` 入口驱动（当前 MCP 参数 schema 未刷新时，经同一 `AiscControlMcpTool` 调用）；`aisc_debug.player_reply_suggestion_snapshot` 返回以下真实 LLM trace：
  - 鹿岛樱：`reply_8c6135eca814`、`reply_1601b5608fda`
  - 千早：`reply_7dafa3da70b5`、`reply_f49de1ec262a`
  - 和叶：`reply_f5f61168f083`、`reply_97016581032c`
  - 龙之介：`reply_b556087a7e9a`、`reply_3af5c78459c3`
  - 九条莲：`reply_338182d181a5`、`reply_906639a7c25f`
- 上述 10 条 trace 均为 `speaker_role_expected=player`、`recipient_role_expected=npc`、`choice_count=3`，无 NPC 名称前缀或开头括号动作，`rejection_reasons=[]`、`fallback_used=false`、`failure_reason=""`。

## 问题与未完成项

- Play Mode Console 在新游戏后出现 4 条既有 NPC 行为请求的 `stale_or_unknown_request` warning；与快捷回复生成无关，本轮未改动该行为链。
- 无未完成的快捷回复主体契约、诊断或验证项。
