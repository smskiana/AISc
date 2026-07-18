> 执行记录: [2026-07-10_场景Anchor移动协议_execution.md](2026-07-10_场景Anchor移动协议_execution.md)

# 场景 Anchor 移动协议 — 设计方案

## 需求理解

当前前后端移动协议虽然使用 `location_id`，但 Unity 侧仍通过 `location_positions.json` 将 ID 解析成世界坐标。这样每次调点位都要改 JSON，不利于在场景里直接拖拽，也没有把“语义位置 ID”和“场景 Transform 落点”职责分清。

本次目标是：

1. 保持后端继续只传 `location_id`
2. Unity 改为优先通过场景中的 Anchor Transform 解析位置
3. 允许后续直接在 Unity 场景里拖点位，不再依赖 JSON 作为主要运行时来源
4. 保留 JSON 作为迁移期 fallback，避免一次性切断现有链路

## 方案思路

### 1. 新增场景 Anchor 组件

新增 `SceneAnchor.cs`：

- 每个 Anchor 挂在场景中的一个 GameObject 上
- 记录 `LocationId`
- 可配置随机偏移半径 `RandomOffsetRadius`
- 负责在 Scene 里以 Gizmos 方式可视化

### 2. 新增 Anchor 注册表

新增 `SceneAnchorRegistry.cs`：

- 启动或首次查询时扫描场景内所有 `SceneAnchor`
- 建立 `location_id -> SceneAnchor` 字典
- 提供：
  - `TryGetPosition`
  - `GetPositionWithOffset`
  - `HasAnchor`
  - `GetAnchor`
  - `MarkDirty / Rebuild`

### 3. 改造 LocationDatabase

保留 `LocationDatabase` 这个入口，避免大量调用点重写，但内部逻辑改为：

1. 优先查 `SceneAnchorRegistry`
2. 查不到时 fallback 到 `location_positions.json`

这样 `NpcEntity` / `NpcSpawner` 现有逻辑基本不动，只切换数据来源。

### 4. 场景初始化

通过 Unity Editor 执行脚本，在 `SampleScene` 中创建一个统一的 `SceneAnchors` 根节点，并基于当前 `location_positions.json` 批量生成所有 Anchor：

- 初始位置直接沿用 JSON，保证行为结果不跳变
- 后续由美术/关卡在场景中直接拖拽微调

### 5. 最小侵入原则

后端协议字段本次不改名：

- `NPC_BEHAVIOR.behavior.location_id`
- `GAME_READY.player_location`
- `DIALOGUE_START.player_location`

原因：

- 后端 `location_id` 已深度进入行为、对话、记忆、存档、地点语义
- 本次真正需要替换的是 Unity 的坐标解析机制，而不是语义 ID 协议本身

## 涉及文件

### 新增

- `Assets/Scripts/Data/SceneAnchor.cs`
- `Assets/Scripts/Data/SceneAnchorRegistry.cs`
- `docs/AIChanges/Navigation/2026-07-10_场景Anchor移动协议_execution.md`

### 修改

- `Assets/Scripts/Data/LocationDatabase.cs`
- 视需要补充 `Assets/Scripts/Core/GameManager.cs` 以提前重建 Anchor 缓存
- `Assets/Scenes/SampleScene.scene`（新增 Anchor 根节点及子节点）

## 风险点

1. 场景中若出现重复 `location_id`，需要注册表给出警告并采用首个或最后一个定义
2. `DontDestroyOnLoad` 的 `GameManager` 与后续切场景时可能让缓存过期，因此注册表需要可重建
3. 迁移期同时存在 JSON 和 SceneAnchor 两套来源，日志里要明确当前实际取的是哪一侧
