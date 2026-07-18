# Assets 目录总索引补齐执行记录

> 设计方案: [2026-07-17_assets_directory_index_plan.md](2026-07-17_assets_directory_index_plan.md)

## 实际改动

1. 新增 `Assets/README.md`，作为 Unity 客户端代码与游戏资产的总入口。
2. 按功能概括脚本、场景、Prefab、数据、Resources、视觉资产、字体、材质、Shader、测试、第三方内容和截图目录。
3. 将脚本定位继续路由到 `Assets/Scripts/README.md`，未复制既有细分脚本索引。
4. 明确纯素材叶子文件、第三方目录和 Unity 管理目录不机械补 README。
5. 将 `docs/ProjectIndex.md` 中 `Assets/` 的入口由 `Assets/Scripts/README.md` 改为 `Assets/README.md`。
6. 通过 Unity MCP 刷新 AssetDatabase；Unity 已将新 README 导入为 `UnityEngine.TextAsset` 并生成 `Assets/README.md.meta`。

## 文档与索引同步

- `docs/ProjectIndex.md` 已指向新的资产总入口。
- `docs/Workstreams/ProjectGovernance/README.md` 的既有口径已经覆盖“受维护目录通过 README 说明功能、内容和入口”，无需重复增加同义条目。
- 未修改 Roadmap；本轮不涉及排期或跨系统路线。
- 未新增或修改 ADR；本轮落实 ADR-0005 的现有功能目录索引口径，不改变系统边界。

## 验证

1. 检查 `Assets/README.md` 中全部 Markdown 本地链接，目标文件均存在。
2. 检查 `docs/ProjectIndex.md`，确认 `Assets/` 主入口为 `Assets/README.md`。
3. 通过 Unity MCP 查询 `Assets/README.md`，确认资产类型为 `UnityEngine.TextAsset`。
4. Unity MCP 刷新完成后编辑器恢复 idle，Console 错误数为 0。
5. 检查 `Assets/README.md.meta` 已生成。

## 诊断与控制钩子

本轮只改变开发文档与目录导航，不修改运行时功能、业务语义、协议、关键状态或失败原因，因此 `aisc_debug`、`aisc_control`、诊断 DTO 和相关测试均不适用，无需同步修改。

## 问题与处理

- 初次写入时发现从 `Assets/README.md` 指向 `docs/` 的相对路径需要先返回项目根目录，已统一修正为 `../docs/...` 并重新验证。

## 未完成项

无。未处理资产重命名、目录重组和既有素材命名债，符合本方案边界。
