# 测试与诊断执行证据

## 文件夹功能

保存跨系统跑测、诊断、性能和迁移验证记录。

## 文件夹内容

- 长时间跑测和复测
- 日志编码、诊断脚本和性能优化
- 数据库迁移、测试修复和问题回归
- Unity 项目专用 MCP 诊断工具、结构化运行快照和协议轨迹

## 当前 Unity 诊断入口

- `Assets/Scripts/Diagnostics/README.md`: Unity 运行时结构化诊断模块入口。
- `aisc_debug`: 项目专用 Unity MCP 工具；`runtime_snapshot.pause` 当前包含 Gameplay/UI/FX 分域状态、来源、`Time.timeScale` 与受管 FX 计数。
- `aisc_control`: 仅编辑器存在的白名单 Unity MCP 控制工具；暂停回归使用固定来源的 `request_pause_test` / `release_pause_test`，不接受任意来源或时间域参数。

## 强制同步口径

1. AI 调试 Unity 运行时功能时优先调用 `aisc_debug`，再结合 Console、测试和其他 Unity MCP 能力验证。
2. 新增或修改功能时必须同步检查对应关键状态、阶段、失败原因和关联 ID 是否可被结构化诊断读取。
3. 业务语义变化时同步修改诊断 DTO、provider、MCP action、测试和入口文档；未同步完成不得视为功能完成。
4. 确实不适用诊断钩子的改动必须在 execution 中明确记录原因。

原始日志和数据库产物放在 `docs/AIChanges/artifacts/`，本目录只保存可阅读的方案与结论。

当前用于记忆路由广度/深度测试的真实运行数据源位于 `docs/AIChanges/artifacts/memory_route_day3_source/`；其权威时间上下文以目录内 `manifest.json` 的 `runtime_snapshot` 为准。

用户继续运行后的更新快照位于 `docs/AIChanges/artifacts/memory_route_day4_current_source/`；需要更多节点、融合来源和玩家交互时优先使用该副本，保留 Day 3 副本用于前后对照。
