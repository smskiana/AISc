# Pause 脚本目录

## 文件夹功能

集中管理多来源暂停以及 Gameplay、UI、FX 三个时间域，业务模块不得直接修改 `Time.timeScale`。

## 核心入口

- `PauseController.cs`：多来源申请/释放、分域状态和 Python 游戏暂停同步。
- `PauseModel.cs`：来源及其时间域的纯状态模型。
- `PauseTimeDomain.cs`：Gameplay、UI、FX 时间域定义。
- `PauseSourcePolicy.cs`：稳定暂停来源到时间域的集中映射。
- `PauseClock.cs`：UI 等非游戏逻辑消费者的分域帧时间入口。
- `PauseFxAdapter.cs`：明确连线的 ParticleSystem/Animator FX 域适配器。
- `PauseSources.cs`：跨模块稳定暂停来源 ID。

## 修改约束

1. 新增暂停来源时必须在 `PauseSources` 与 `PauseSourcePolicy` 同步声明。
2. 游戏主逻辑显式判断 `Gameplay`；UI 动效使用 `PauseClock` 的 `UI` 域。
3. FX Prefab、场景组件和 SerializeField 连线必须通过 Unity MCP 完成。
4. 时间域语义变化必须同步 `aisc_debug`、`aisc_control`、测试和前端 Workstream。
