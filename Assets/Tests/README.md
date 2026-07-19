# Unity 测试目录

## 文件夹功能

保存 Unity EditMode / PlayMode 自动化测试。测试按被测功能和稳定类名组织，不按日期创建目录。

## 何时使用

- 纯 C# 规则、DTO、状态机、拒绝原因和确定性逻辑优先使用 EditMode 测试。
- 依赖场景生命周期、真实移动、MonoBehaviour 更新或前后端运行链时使用 PlayMode 测试。
- 需要稳定触发正式业务 seam 或读取结构化结果时，组合使用 `aisc_control` 与 `aisc_debug`，具体 action 见 `Assets/Scripts/Diagnostics/README.md`。

## 使用规则

1. 先按被测符号或功能名筛选现有测试类，只运行相关测试作为聚焦门禁。
2. 改动触及共享状态、协议或多个模块时，再扩大到相关程序集或完整 EditMode / PlayMode 套件。
3. Unity 测试必须通过 Unity Test Runner 或 Unity MCP 的测试能力运行；不要用普通 .NET runner 代替 Unity 生命周期。
4. 场景、Prefab、SerializeField 和 UI 层级问题先遵循 `docs/DesignDocs/UnityMCPUsageRules.md`，不得用测试运行时代码补资产连线。
5. 测试结果应记录测试模式、筛选条件、通过/失败/跳过数量和关键失败信息；结构化业务状态另用 `aisc_debug` 取证。

## 当前入口

- `Editor/`：现有 EditMode 回归，覆盖诊断、游戏状态、NPC 日程、NPC 运行时状态、社交预留、暂停时间域和系统消息加载进度。
- 项目白名单 Play Mode probe：入口和限制见 `Assets/Scripts/Diagnostics/README.md`。

新增测试前先用 codebase-memory 或 `rg` 查找同一被测类型的既有覆盖，优先扩展现有测试类。
