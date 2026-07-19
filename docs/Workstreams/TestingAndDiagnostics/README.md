# 工作流：测试与诊断

## 当前目标

让 AI 在制定验收或开始测试前先发现项目已有工具，并按任务风险选择最小充分的验证组合。本文只负责选择和路由；具体命令、action、测试类和限制继续由工具所属目录的 README 维护。

## 分级阅读顺序

1. 先读本文，判断需要哪类证据。
2. 只读取所选工具对应的叶子 README。
3. 用 `rg`、codebase-memory 或测试运行器筛选与改动直接相关的测试和 action，不批量阅读全部测试代码或工具说明。
4. 只有聚焦验证暴露跨模块风险时，才扩大到组合测试、真实 Play Mode 或长跑。

## 工具选择表

| 验证目标 | 优先工具 | 叶子入口 |
|----------|----------|----------|
| Unity 纯 C# 规则、DTO、状态机和回归 | Unity EditMode 测试 | `Assets/Tests/README.md` |
| Unity 场景内生命周期、移动、UI 或真实协议链 | Unity PlayMode / 项目白名单 Play Mode probe | `Assets/Tests/README.md`、`Assets/Scripts/Diagnostics/README.md` |
| Python 单元、集成、协议和数据语义 | pytest / unittest 聚焦测试 | `backend/tests/README.md` |
| 多日运行、性能、离线检索评估或配置调优 | 后端跑测与诊断脚本 | `backend/scripts/README.md` |
| Unity 运行时关键状态、阶段、失败原因和关联 ID | `aisc_debug` 结构化快照 | `Assets/Scripts/Diagnostics/README.md` |
| 需要可重复触发正式业务 seam 的编辑器测试 | `aisc_control` 白名单 action | `Assets/Scripts/Diagnostics/README.md` |
| Unity 编译错误或无结构化覆盖的编辑器异常 | Console，结合对应自动化测试 | `Assets/Scripts/Diagnostics/README.md` |
| 场景、Prefab、SerializeField、UI 结构和资产连线 | Unity MCP 资产层检查 | `docs/DesignDocs/UnityMCPUsageRules.md` |

测试工具可以组合使用，但必须说明每种工具覆盖的风险；不得把“把所有工具都跑一遍”当作测试方案。已有 `aisc_debug` 结构化状态时，不得只凭 Console 文本推断业务结果。

## 独立测试会话

1. 读取同主题 plan 的验收标准和 execution 的实际改动，不重新设计功能。
2. 从上表选择最小充分工具，并只读取对应叶子入口。
3. 先跑聚焦验证，再按失败或跨模块风险扩大范围。
4. 创建同主题 `_test.md`，链接 plan 与 execution，记录环境、选择理由、步骤、证据、结果和未覆盖项。
5. 测试通过后才能认定复杂任务整体完成；失败时回到新的执行会话修复，测试会话不顺手修改实现。

## 当前工程口径

1. 实现会话内的编译、静态检查、聚焦测试和诊断冒烟属于最低门禁，不替代独立测试。
2. `_test.md` 按主要功能域存放；跨系统纯跑测或诊断任务才进入 `docs/AIChanges/TestingAndDiagnostics/`。
3. 新功能或业务语义变化必须同步评估 `aisc_debug` / `aisc_control`、自动化测试和入口文档；不适用时在 execution 与 test 中说明原因。
4. 原始日志、数据库副本和大体积摘要放入 `docs/AIChanges/artifacts/`，test record 只保存可读结论和产物链接。

## 相关入口

1. `Assets/Tests/README.md`
2. `backend/tests/README.md`
3. `backend/scripts/README.md`
4. `Assets/Scripts/Diagnostics/README.md`
5. `docs/AIChanges/TestingAndDiagnostics/README.md`
