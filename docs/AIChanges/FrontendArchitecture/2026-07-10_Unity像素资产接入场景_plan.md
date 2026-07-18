> 执行记录: [2026-07-10_Unity像素资产接入场景_execution.md](2026-07-10_Unity像素资产接入场景_execution.md)

# Unity 像素资产接入场景 — 设计方案

## 需求理解

用户希望继续把两类已生成资源真正接进 Unity：

1. `PixelCharacters` 挂到 Player / NPC prefab
2. `PixelScenes` 接进 `SampleScene`，形成实际可见场景替换

## 当前观察

- `Player.prefab` 与 5 个 NPC prefab 均已有 `SpriteRenderer`，适合直接替换 sprite
- 新像素角色图已导入为 Sprite，但当前 `PPU=100`
- 新像素角色画布为 `1254x1254`，若直接替换且不调尺寸，会比旧 `char_*.png` 大很多
- `SampleScene` 当前存在可运行的 Player / Dialogue / GameManager 体系
- `SceneRoot` 和 `Grid_map` 都是 inactive，说明当前视觉层可以较安全地新增而不必强拆旧内容
- 场景中同时存在两套启用状态的 `NpcSpawner/NpcBubbleManager`
  - 一套挂在 `GameManager`
  - 一套为单独空物体
  - 两套 prefab 引用都已填写，存在运行时双重处理风险

## 方案思路

### 1. PixelCharacters 接 prefab

对 `Assets/Art/Generated/PixelCharacters/*.png`：

- 调整为更适合世界内角色的 `spritePixelsPerUnit`
- 保持点过滤与无压缩

随后修改：

- `Assets/Prefabs/Player/Player.prefab`
- `Assets/Prefabs/NPCs/01_Sakura.prefab`
- `Assets/Prefabs/NPCs/02_Chihaya.prefab`
- `Assets/Prefabs/NPCs/03_Kazuha.prefab`
- `Assets/Prefabs/NPCs/04_Tatsunosuke.prefab`
- `Assets/Prefabs/NPCs/05_Kujo.prefab`

将各自 `SpriteRenderer.sprite` 切到对应像素角色图，并把 `color` 统一恢复为白色，避免旧占位着色污染新像素图。

### 2. PixelScenes 接 SampleScene

在 `SampleScene` 中新增 `PixelSceneRoot`：

- `StreetBackdrop`
- `CafeBackdrop`

其中：

- `StreetBackdrop` 默认启用，使用 `street_topdown_map_v1.png`
- `CafeBackdrop` 默认关闭，使用 `player_cafe_topdown_map_v1.png`

主街地图会根据现有 `location_positions.json` 坐标范围进行轻度缩放和偏移对齐，优先服务当前世界路线点和玩家出生位置。

### 3. 重复 Spawner 的保守处理

为避免运行时双倍生成/双倍气泡：

- 保留 `GameManager` 上的 `NpcSpawner/NpcBubbleManager`
- 关闭单独空物体 `NpcSpawner`、`NpcBubbleManager`

这样不删除组件、不改代码，只收敛到已配置完成的一套运行链路。

## 涉及资产 / 场景

- `Assets/Art/Generated/PixelCharacters/*.png`
- `Assets/Prefabs/Player/Player.prefab`
- `Assets/Prefabs/NPCs/*.prefab`
- `Assets/Scenes/SampleScene.scene`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity像素资产接入场景_execution.md`

## 风险点

1. 像素角色原图画布较大，PPU 需要按现有效果折中处理
2. 主街整图只是视觉层，不会自动生成新的碰撞/可行走区
3. 关闭重复的 `NpcSpawner/NpcBubbleManager` 会改变现有场景执行路径，但这是为规避明显的双重订阅风险
