> 设计方案: [2026-07-10_场景Anchor移动协议_plan.md](2026-07-10_场景Anchor移动协议_plan.md)

# 场景 Anchor 移动协议 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已完成 Unity 侧“`location_id` → 场景 Transform”迁移的第一阶段落地：

1. 新增场景 Anchor 组件与注册表
2. `LocationDatabase` 改为优先读取场景 Anchor、JSON 仅作 fallback
3. `GameManager` 启动时主动重建 Anchor 缓存
4. 在 `SampleScene` 中批量生成 45 个场景 Anchor

本次没有改动后端协议字段名，后端仍然只传 `location_id`。

## 实际改动清单

### 新增脚本 (2)

- `Assets/Scripts/Data/SceneAnchor.cs`
- `Assets/Scripts/Data/SceneAnchorRegistry.cs`

### 修改脚本 (2)

- `Assets/Scripts/Data/LocationDatabase.cs`
- `Assets/Scripts/Core/GameManager.cs`

### 修改场景 (1)

- `Assets/Scenes/SampleScene.scene`

### 新建文档 (2)

- `docs/AIChanges/Navigation/2026-07-10_场景Anchor移动协议_plan.md`
- `docs/AIChanges/Navigation/2026-07-10_场景Anchor移动协议_execution.md`

## 实现细节

### 1. SceneAnchor

`SceneAnchor` 负责把一个 `location_id` 绑定到场景中的一个 `Transform`：

- 字段：
  - `LocationId`
  - `RandomOffsetRadius`
- 生命周期：
  - `OnEnable / OnDisable / OnValidate` 都会触发 `SceneAnchorRegistry.MarkDirty()`
- 可视化：
  - 在 Scene 视图用 `Gizmos` 画出锚点和偏移半径

### 2. SceneAnchorRegistry

`SceneAnchorRegistry` 负责场景内所有 Anchor 的运行时缓存：

- `Rebuild()`：扫描全部 `SceneAnchor`
- `GetAnchor()`：按 `location_id` 取组件
- `GetPosition()`：取 Anchor 的 XY 世界坐标
- `GetPositionWithOffset()`：按 Anchor 半径生成随机落点
- `TryResolveNearestLocation()`：预留给未来玩家位置反查

重复 ID 会给出 warning，后出现的 Anchor 覆盖前者。

### 3. LocationDatabase 改造

保留原有 `LocationDatabase` 调用入口，避免大面积修改旧逻辑，但内部来源改为：

1. 先查 `SceneAnchorRegistry`
2. 查不到再读 `location_positions.json`

因此 `NpcEntity.MoveToLocation()` / `TeleportTo()` 等现有调用点无需重写即可切换到新体系。

### 4. GameManager 初始化

在 `GameManager.Start()` 中增加：

- `SceneAnchorRegistry.Rebuild()`
- `LocationDatabase.Load()`

确保进入游戏后先建立场景 Anchor 缓存，再加载 fallback JSON。

### 5. 场景 Anchor 批量落地

通过 Unity Editor 内联执行代码，在 `SampleScene` 中创建：

- 根节点：`SceneAnchors`
- 子节点：45 个 `location_id` 对应的 Anchor GameObject

初始坐标直接沿用原 `location_positions.json` 的数值，确保迁移前后行为结果一致。

## 验证结果

### 编译 / 控制台

- [x] Unity 脚本刷新完成
- [x] 无新增编译错误
- [x] 当前控制台仅保留既有 warning：
  - `Assets/Scripts/Core/GameManager.cs(15,37)` 的 `_serverUrl` 未使用

### 运行时验证

已用 Unity Editor 内联代码验证：

- `sceneAnchorCount = 45`
- 以下点位都能通过 `LocationDatabase.GetPosition()` 命中场景 Anchor：
  - `player_cafe.doorway`
  - `flower_shop.counter`
  - `street.crossroad`
  - `park.entrance`
  - `riverside.path`

### 场景落盘验证

`Assets/Scenes/SampleScene.scene` 中已可看到：

- `SceneAnchors`
- `player_cafe.doorway`
- `flower_shop.counter`
- `street.crossroad`
- `park.entrance`
- `riverside.path`

## 说明

### 当前职责边界

- 后端：继续维护并发送语义位置 ID（`location_id`）
- Unity：负责把 `location_id` 解析为场景中的 `Transform`

### 为什么保留 JSON fallback

为了降低迁移风险，本次没有直接删除 `location_positions.json` 依赖：

- 新场景未补 Anchor 时仍可工作
- 旧逻辑不会因单个 Anchor 漏配而立即崩溃
- 便于逐步迁移其他场景

## 未完成项

1. 还没有删除 `location_positions.json`
2. 玩家移动仍未主动上报 `PLAYER_MOVE {location_id}`
3. 当前 Anchor 是按旧 JSON 坐标自动生成，后续仍需要你在 Scene 里按美术布局微调
4. 还没有做“从玩家当前世界坐标反查最近 Anchor”的正式接线

## 下次建议起点

1. 在 Scene 视图直接拖拽 `SceneAnchors` 下的关键点位，验证 NPC 行为是否能跟着走
2. 把玩家移动完成后的当前位置解析接到 `PLAYER_MOVE`
3. 当场景 Anchor 覆盖率稳定后，再考虑是否彻底移除 JSON fallback
