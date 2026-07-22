# codebase-memory-mcp 更新状态

- 最近更新时间：2026-07-22 16:25:49 +08:00
- 项目索引库：AISc（零 LLM 确定性查询切换执行工作树）；AISc_r3v2_runtime_retest_20260721（修复后独立复测验证索引）；AISc_r3v2_runtime_fix_20260721（独立测试失败修复后的当前工作树验证索引）；AISc_r3v2_runtime_20260721；AISc_memory_route_training_20260720；AISc_save_schema_fix_20260719；AISc_two_segment_stage5_20260719；AISc_two_segment_stage1_20260719；AISc_replan_expiry_fix_20260719；AISc_replan_fix_20260719；AISc_world_prep_fix_20260719
- 项目路径：F:/GameProject/unity/AISc
- 最近索引结果：canonical `AISc` moderate + persistence 最终刷新为 11514 nodes / 27069 edges，actual 与 expected 完全一致；压缩图已写入 `.codebase-memory/graph.db.zst`。当前索引配置排除 `docs/`、`backend/scripts/`、`backend/tests/fixtures/`、训练夹具和测试缓存等目录。
- 本轮代码级结论：Project Cognition 修复 AB02 方法级证据导航后刷新 canonical `AISc`；`tools/` 仍被排除，因此 Method evidence 的同源 label/导航映射由扩展 8 项自动化、15 项 Server 回归、真实 UML smoke 与 VSIX bundle 门禁覆盖。图统计保持 11514 nodes / 27069 edges。
