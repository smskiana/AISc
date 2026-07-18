> 设计方案: [2026-07-11_开始界面减重与资产化_plan.md](2026-07-11_开始界面减重与资产化_plan.md)

# 开始界面减重与资产化 — 执行记录

## 完成时间

2026-07-11

## 本次完成内容

本轮把原本接近 700 行、同时承担 View 构建和业务流程的开始界面实现拆成了“控制层 + 视图层 + 后端辅助 + 编辑器 Builder”，并通过 Unity MCP 真正把开始界面落到了 `Town_Main.scene` 和 UI 预制体中。

同时已把用户指定背景：

- `Assets/Art/Generated/PixelScenes/street_arcade_pixel_v1.png`

作为开始界面的真实 `Image.sprite` 资源接入，而不是再由运行时代码读磁盘文件生成。

## 实际改动清单

### 新增脚本 (4)

1. `Assets/Scripts/Core/StartMenuBackendLauncher.cs`
   - 拆出后端 health 检查、健康等待和 Python 拉起逻辑
2. `Assets/Scripts/Core/StartMenuView.cs`
   - 承载开始界面所有 SerializeField 引用
   - 负责状态文案、显隐、交互态和存档列表渲染
3. `Assets/Scripts/Core/StartMenuSaveButtonView.cs`
   - 承载单个存档按钮预制体的文案和点击绑定
4. `Assets/Scripts/Editor/StartMenuBuilder.cs`
   - 新增 `Tools/Build Start Menu`
   - 负责构建开始界面场景节点、预制体与控制器连线

### 修改脚本 / 索引 (2)

1. `Assets/Scripts/Core/StartMenuController.cs`
   - 从原先 694 行的“巨型类”收口为纯控制层
   - 不再运行时创建 Canvas / Button / Input / 背景图
   - 只保留：
     - GameManager 事件订阅
     - 后端启动 / 连接 / 读档流程编排
     - 按钮点击业务处理
     - 对 `StartMenuView` 的刷新调用
2. `Assets/Scripts/Index.md`
   - 回写新增开始界面脚本和 Builder 入口

### Unity 资产层落地结果

通过 Unity MCP 执行 `Tools/Build Start Menu` 后，已生成并连线：

1. 场景对象
   - `cvs_startMenu_dy`
   - `go_startMenuController_dy`
2. 预制体
   - `Assets/Prefabs/UI/UI_StartMenuCanvas.prefab`
   - `Assets/Prefabs/UI/UI_StartMenuSaveButton.prefab`
3. 背景图引用
   - `img_startBackground_dy` 的 `Image.sprite`
   - 指向 `Assets/Art/Generated/PixelScenes/street_arcade_pixel_v1.png`
4. 脚本引用
   - `StartMenuController._view` 已连到 `cvs_startMenu_dy`
   - `StartMenuView` 内各按钮、输入框、空列表提示、存档列表内容根节点、存档按钮预制体均已完成 SerializeField 连线

## MCP 执行与验证

### Unity 会话

- 已确认实例：`AISc@9db8baa7dcf9cfcd`
- Unity 版本：`2022.3.62t7`

### 脚本校验

已通过 `validate_script` 校验：

1. `Assets/Scripts/Core/StartMenuController.cs`
2. `Assets/Scripts/Core/StartMenuView.cs`
3. `Assets/Scripts/Editor/StartMenuBuilder.cs`

结果：

- `0 error`
- `0 warning`

### Console 检查

本轮开始界面相关构建完成后，Console 关键信息：

1. `[StartMenuBuilder] 开始界面构建完成。`
2. 无新增开始界面相关编译错误

仍存在的旧 warning：

1. `Assets/Scripts/Core/GameManager.cs(15,37): warning CS0414`
   - `_serverUrl` 已赋值但未使用

该 warning 与本轮开始界面改动无直接冲突，未在本轮顺手处理。

## 结构结果

### 改动前

`StartMenuController` 同时承担：

1. 运行时搭 UI
2. 读背景图
3. 管按钮
4. 渲染存档列表
5. 检查 health
6. 拉起 Python
7. 编排 GameManager 流程

### 改动后

职责拆分为：

1. `StartMenuController`
   - 流程编排
2. `StartMenuView`
   - View 引用与渲染
3. `StartMenuSaveButtonView`
   - 单项按钮视图
4. `StartMenuBackendLauncher`
   - 后端启动辅助
5. `StartMenuBuilder`
   - 资产层构建与引用连线

## 未完成项

1. 本地“登录名”仍只写 `PlayerPrefs`，没有继续同步到后端玩家称呼
2. 本轮没有进入 Play 模式完整跑一遍“启动后端 → 连 WS → 列存档 → 新游戏 / 载入存档 → GAME_READY”的端到端交互

## 下次建议起点

1. 直接在 Unity 里进 Play，验证开始界面完整链路
2. 若要继续做视觉优化，优先改：
   - `Assets/Prefabs/UI/UI_StartMenuCanvas.prefab`
   - `Assets/Prefabs/UI/UI_StartMenuSaveButton.prefab`
   - `Assets/Scripts/Editor/StartMenuBuilder.cs`
3. 若要把玩家名继续下沉到后端协议，再单独开一轮“开始界面登录名同步”
