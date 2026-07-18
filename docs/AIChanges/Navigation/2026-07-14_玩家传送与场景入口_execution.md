# 玩家传送与场景入口执行记录

> 设计方案: [plan.md](2026-07-14_玩家传送与场景入口_plan.md)

## 实际改动清单

1. 新增 `PlayerTeleportController`：扫描当前场景传送端点，按距离选择触发半径内最近入口，响应 F 并移动到配对出口。
2. 入口方向遵守 `ExportsLink` / `Bidirectional`：导出端可进入；非导出端只有在配对导出端允许双向时才可反向进入。
3. 新增 `PlayerLocationResolver`：仅在游戏就绪且未进入对话时周期解析玩家 `SceneAnchor`，传送结束后强制立即同步一次地点。
4. 新增 `PlayerTransitionView`：只驱动资产层提示节点的文本和显隐。
5. `PlayerController` 移除原有地点同步字段和轮询函数，避免继续承担地点解析职责。
6. `GameManager` 的测试快进键由 F 改为 F8，F 留给玩家场景交互。

## Unity 资产修改

1. 使用 Unity MCP 在 `Town_Main` 新建 `cvs_playerTransition_dy`。
2. Canvas 下创建默认隐藏的 `pnl_playerTransition_dy` 和 `txt_playerTransition_dy`，显示文本为“按 F 前往”。
3. TMP 字体使用 `Assets/Fonts/MSYH SDF.asset`，Canvas 使用 1280x720 Scale With Screen Size，sorting order 为 80。
4. `player_dy` 新增 `PlayerLocationResolver` 与 `PlayerTeleportController`。
5. `PlayerTeleportController._transitionView` 已连到 Canvas 上的 `PlayerTransitionView`；视图的 `_root` / `_label` 已连到提示面板和 TMP 文本。
6. 复用 `go_tranport_st` 下原有 16 个 `NavigationTeleportPoint`，未复制玩家专用触发区。
7. 已保存 `Assets/Scenes/Town_Main.scene`。

## 遇到的问题

1. Unity MCP 临时代码的 Roslyn 后端不可用，CodeDom 又不引用项目 `Assembly-CSharp`，因此标准 uGUI 结构由临时代码创建，项目脚本由 `manage_components` 挂载和连线。
2. 新脚本仅刷新时未生成 `.meta`，组件接口无法识别类型；改为逐个 `manage_asset import` 后编译成功。该问题已记录到 `docs/DesignDocs/errors/2026-07-14_unity_mcp_new_script_requires_import.md`。

## 验证方式

1. Unity 强制导入并编译三个新脚本，Console 0 error。
2. 资产读取确认 `player_dy` 上存在两个新组件，传送控制器引用有效。
3. 资产读取确认提示 Canvas、面板、TMP 文本、中文字体、默认隐藏状态和视图引用有效。
4. Play Mode 反射调用提示与传送入口：
   - `promptShown=True`
   - 从 `street_cafe` 街道端传送后 `actual=(-12.00, -4.74)`，与配对出口 `expected=(-12.00, -4.74)` 一致。
   - 传送后 `promptHidden=True`。
5. Play Mode 检查场景传送点：`scenePoints=16`，按当前双向配置 `enterablePoints=16`。
6. Play Mode Console 0 error，验证完成后正常退出 Play Mode。

## 文档回写

1. 更新 `Assets/Scripts/Navigation/README.md`。
2. 更新 `Assets/Scripts/UI/README.md`。
3. 更新 `docs/Workstreams/Navigation/README.md`，将玩家传送标记为已完成。
4. 更新错误预防索引。
5. 补充更新 `docs/Roadmap.md`、`docs/Workstreams/FrontendArchitecture/README.md`、`docs/DesignDocs/CodebaseBigPicture.md`、`docs/Workstreams/README.md` 和 `docs/ProjectIndex.md`，清除仍将玩家传送标记为待办的当前口径。

## 未完成项

1. 本轮未通过物理键盘自动化注入真实 F 按键；输入分支使用 Unity 既有 `Input.GetKeyDown(KeyCode.F)`，核心提示与传送方法已在 Play Mode 验证。
2. 当前提示文案固定为“按 F 前往”，未增加地点显示名；后续如需要目的地名称，应从稳定 location 配置读取，不能从 GameObject 名称推导。
