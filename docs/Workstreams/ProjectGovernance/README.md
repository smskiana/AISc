# 工作流：项目治理

## 当前目标

维护已经落地的“功能目录 + 路线图 + Workstream + ADR + 执行证据”体系，确保当前状态及时从 execution 回写到工程口径。

## 当前工程口径

1. `docs/ProjectIndex.md` 是总入口。
2. `docs/Roadmap.md` 管长期方向与当前阶段。
3. `docs/Workstreams/*/README.md` 管系统状态和下一步。
4. `docs/DecisionRecords/ADR-*.md` 管已收敛的架构决定。
5. `docs/AIChanges/<功能域>/` 保存实际实现修改的 plan / execution / test，并作为证据库。
6. `docs/AIChanges/ChangeIndex.md` 只负责功能目录路由，不维护日期长表。
7. 每个受维护目录通过 README 说明文件夹功能、内容和入口。
8. handoff 归档到 `docs/AIChanges/Archive/Handoffs/`，不再作为默认上下文。
9. Unity 运行时功能的 AI 调试优先使用项目专用 `aisc_debug`；修改功能时必须同步评估、补齐并验证对应诊断钩子，未同步完成不得视为交付完成。
10. 已触发 plan 的复杂修改分为执行案、执行记录、测试记录三个独立会话；execution 只表示实现完成并通过最低门禁，独立 test 通过后才表示整体完成。
11. 测试工具按 `docs/Workstreams/TestingAndDiagnostics/README.md` 分级发现；顶层规则不复制具体工具参数和 action 清单。
12. 项目认知 MCP 与 IDE 适配已拆分到 `docs/Workstreams/ProjectCognition/README.md`，本 Workstream 只维护其索引和治理边界。

## 已完成阶段

1. 已建立 `ProjectIndex.md` 和 `DesignDocs/Index.md`。
2. 已建立 `AIChanges/README.md` 并把 artifacts 从根层分离。
3. 已补 `CodebaseBigPicture.md`，说明代码层职责边界。
4. 本轮新增 Roadmap / Workstreams / ADR / ChangeIndex。
5. 已将 AIChanges 历史记录迁入功能目录，并建立项目、文档、代码模块的目录说明。
6. 已新增 ADR-0005，固定功能目录优先的文档治理方式。
7. 已完成首轮 Roadmap 与 Workstream 状态回写，移除已完成职责拆分和协议闭环的过期待办。
8. 已将 AI 诊断钩子的使用与同步维护纳入 `AGENTS.md` 项目级硬约束。

## 下一阶段建议

1. 后续每次非平凡实际实现修改直接在主要功能目录创建 plan / execution / test，并标注所属 Workstream。
2. 纯讨论、方案草案、排期安排和优先级调整不创建 plan / execution / test；需要落文档时直接更新 Roadmap、Workstream 或设计文档。
3. 每轮完成阶段性能力后，把功能证据目录中的有效结论及时回填到 Roadmap 和对应 Workstream。
4. 如果某个 ADR 被推翻，新增 superseding ADR，而不是直接抹掉历史决定。
5. 维护自动检查，验证目录 README、plan / execution / test 互链和 Markdown 本地链接。
6. 后续功能实现的 execution 必须记录对应诊断钩子的新增、修改、验证结果，或明确说明不适用原因。
7. 后续独立测试会话先从测试与诊断 Workstream 选择现有工具，只读取所选叶子入口，并在 test record 记录选择理由和证据。

## 暂缓事项

1. 不移除执行证据文件名中的日期审计信息。
2. 不为 Unity 生成目录、第三方包和纯素材叶子目录机械添加 README。
3. 不立即建设文档向量库。

## 相关入口

1. `docs/Roadmap.md`
2. `docs/DecisionRecords/ADR-0004-document-governance-and-vector-index.md`
3. `docs/AIChanges/ChangeIndex.md`
4. `docs/AIChanges/ProjectGovernance/README.md`
5. `docs/DecisionRecords/ADR-0005-functional-document-index.md`
