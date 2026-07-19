# codebase-memory-mcp 更新状态

- 最近更新时间：2026-07-19 16:44:35 +08:00
- 项目索引库：AISc_save_schema_fix_20260719（本轮新鲜索引）；AISc_two_segment_stage5_20260719；AISc_two_segment_stage1_20260719；AISc_replan_expiry_fix_20260719；AISc_replan_fix_20260719；AISc_world_prep_fix_20260719；AISc（既有 canonical）
- 项目路径：F:/GameProject/unity/AISc
- 最近索引结果：6374 nodes / 20408 edges（moderate，新鲜索引已覆盖 Unity 存档 schema 3 仓储校验、2 到 3 migration 和聚焦回归；当前索引配置排除 `docs/`）
- canonical `AISc` 的 moderate/fast 返回成功但抽查仍为旧图，full 连续两次 worker crash；本轮未把陈旧结果误记为成功，后续应在 MCP 索引器修复后合并回 canonical 名称。
