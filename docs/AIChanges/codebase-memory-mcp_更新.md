# codebase-memory-mcp 更新状态

- 最近更新时间：2026-07-22 10:30:58 +08:00
- 项目索引库：AISc（零 LLM 确定性查询切换执行工作树）；AISc_r3v2_runtime_retest_20260721（修复后独立复测验证索引）；AISc_r3v2_runtime_fix_20260721（独立测试失败修复后的当前工作树验证索引）；AISc_r3v2_runtime_20260721；AISc_memory_route_training_20260720；AISc_save_schema_fix_20260719；AISc_two_segment_stage5_20260719；AISc_two_segment_stage1_20260719；AISc_replan_expiry_fix_20260719；AISc_replan_fix_20260719；AISc_world_prep_fix_20260719
- 项目路径：F:/GameProject/unity/AISc
- 最近索引结果：canonical `AISc` moderate + persistence 最终刷新为 11514 nodes / 27069 edges，actual 与 expected 完全一致；压缩图已写入 `.codebase-memory/graph.db.zst`。当前索引配置排除 `docs/`、`backend/scripts/`、`backend/tests/fixtures/`、训练夹具和测试缓存等目录。
- 本轮代码级结论：完成 Project Cognition 第一轮实现前刷新 canonical `AISc`；当前索引默认排除 `tools/`，因此新工具通过自身 codebase-memory 真实 MCP smoke 与 stdio contract 验证，未进入 canonical 图节点。原有生产与测试图统计保持 11514 nodes / 27069 edges。
