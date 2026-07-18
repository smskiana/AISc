> 设计方案: [2026-07-10_Unity像素资产接入场景_plan.md](2026-07-10_Unity像素资产接入场景_plan.md)

# Unity 像素资产接入场景 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已完成以下接入工作：

1. 将 `PixelCharacters` 挂接到 Player 与 5 个 NPC prefab
2. 将 `PixelScenes` 接入 `SampleScene`，形成实际可见的主街像素底图
3. 关闭场景中重复启用的 `NpcSpawner/NpcBubbleManager` 空物体，避免双重处理
4. 修正运行时 NPC 默认 tint，避免新像素图在生成后被再次染色

## 实际改动清单

### 1. 调整像素角色图导入设置 (6)

以下资源统一调整为更适合世界内小人的导入参数：

- `Assets/Art/Generated/PixelCharacters/player_pixel_v1.png`
- `Assets/Art/Generated/PixelCharacters/sakura_pixel_v1.png`
- `Assets/Art/Generated/PixelCharacters/chihaya_pixel_v1.png`
- `Assets/Art/Generated/PixelCharacters/kazuha_pixel_v1.png`
- `Assets/Art/Generated/PixelCharacters/tatsunosuke_pixel_v1.png`
- `Assets/Art/Generated/PixelCharacters/kujo_pixel_v1.png`

应用设置：

- `Texture Type = Sprite (2D and UI)`
- `Sprite Mode = Single`
- `Filter Mode = Point`
- `Compression = Uncompressed`
- `MipMap = false`
- `Alpha Is Transparency = true`
- `Sprite Pixels Per Unit = 1000`

说明：

此前这些角色图虽然已是 Sprite，但 `PPU=100`，直接接到现有 prefab 会导致显示过大。本次将其统一提升到 `1000`，用于贴合现有世界坐标体系。

### 2. 更新 Player prefab (1)

修改：

- `Assets/Prefabs/Player/Player.prefab`

结果：

- `SpriteRenderer.sprite` 改为 `Assets/Art/Generated/PixelCharacters/player_pixel_v1.png`
- `SpriteRenderer.color` 改为白色
- `sortingOrder` 改为 `20`

### 3. 更新 NPC prefab (5)

修改：

- `Assets/Prefabs/NPCs/01_Sakura.prefab`
- `Assets/Prefabs/NPCs/02_Chihaya.prefab`
- `Assets/Prefabs/NPCs/03_Kazuha.prefab`
- `Assets/Prefabs/NPCs/04_Tatsunosuke.prefab`
- `Assets/Prefabs/NPCs/05_Kujo.prefab`

结果：

- 各 prefab 的 `SpriteRenderer.sprite` 切换到对应 `PixelCharacters` 资源
- `SpriteRenderer.color` 统一恢复为白色
- `sortingOrder` 统一改为 `10`

对应关系：

- `01_Sakura.prefab` → `sakura_pixel_v1.png`
- `02_Chihaya.prefab` → `chihaya_pixel_v1.png`
- `03_Kazuha.prefab` → `kazuha_pixel_v1.png`
- `04_Tatsunosuke.prefab` → `tatsunosuke_pixel_v1.png`
- `05_Kujo.prefab` → `kujo_pixel_v1.png`

### 4. 接入场景像素底图 (SampleScene)

修改场景：

- `Assets/Scenes/SampleScene.scene`

新增根物体：

- `PixelSceneRoot`

新增子物体：

- `StreetBackdrop`
- `CafeBackdrop`

配置结果：

#### StreetBackdrop

- Sprite: `Assets/Art/Generated/PixelScenes/street_topdown_map_v1.png`
- Active: `true`
- Position: `(1.25, 0, 0)`
- Scale: `(1.15, 1.15, 1)`
- Sorting Order: `-100`

#### CafeBackdrop

- Sprite: `Assets/Art/Generated/PixelScenes/player_cafe_topdown_map_v1.png`
- Active: `false`
- Position: `(1, 0, 0)`
- Scale: `(1, 1, 1)`
- Sorting Order: `-90`

说明：

- 当前 `SampleScene` 的运行语义更偏主街外景，因此主街底图默认启用
- 喫茶店内景图已预埋到场景，便于后续做室内切换，但本次默认隐藏

### 5. 收敛重复启用的 Spawner / BubbleManager

在场景中发现以下重复根物体与 `GameManager` 上的组件功能重叠：

- `NpcSpawner`
- `NpcBubbleManager`

处理方式：

- 保留 `GameManager` 上已配置好的 `NpcSpawner` / `NpcBubbleManager`
- 将单独根物体 `NpcSpawner`、`NpcBubbleManager` 设为 `inactive`

这样可以避免：

- 双重订阅 `GameManager` 事件
- 重复刷 NPC
- 重复冒泡 / 重复日志

### 6. 修正运行时 NPC 默认着色

问题：

- 虽然 prefab 中的 `SpriteRenderer.color` 已改成白色
- 但 `NpcSpawner` 在运行时会通过 `_colorSakura / _colorChihaya / ...` 再次给 NPC 默认上 tint

处理：

将 `SampleScene` 中 `GameManager` 上那套实际启用的 `NpcSpawner` 颜色字段统一改为白色：

- `_colorSakura`
- `_colorChihaya`
- `_colorKazuha`
- `_colorTatsunosuke`
- `_colorKujo`

结果：

- NPC 空闲默认状态保持原始像素图颜色
- 不再被粉色 / 黄色 / 绿色等占位色覆盖

## 验证结果

### 已完成验证

- [x] 6 张像素角色图导入参数已更新
- [x] `Player.prefab` 已改引用 `player_pixel_v1.png`
- [x] 5 个 NPC prefab 已改引用对应像素角色图
- [x] 场景中已存在 `PixelSceneRoot/StreetBackdrop/CafeBackdrop`
- [x] `StreetBackdrop` 已默认启用
- [x] `CafeBackdrop` 已默认隐藏
- [x] 单独根物体 `NpcSpawner` / `NpcBubbleManager` 已关闭
- [x] `GameManager` 上 `NpcSpawner` 的默认角色色已改为白色
- [x] Unity Console 当前无 error / warning / log 新增异常

### 抽样验证

1. `Assets/Prefabs/Player/Player.prefab`
   - `SpriteRenderer.m_Sprite` 已指向 `player_pixel_v1.png`
   - `m_SortingOrder = 20`
   - `m_Color = white`

2. `Assets/Prefabs/NPCs/01_Sakura.prefab`
   - `SpriteRenderer.m_Sprite` 已指向 `sakura_pixel_v1.png`
   - `m_SortingOrder = 10`
   - `m_Color = white`

3. `Assets/Art/Generated/PixelCharacters/player_pixel_v1.png.meta`
   - `spritePixelsToUnits: 1000`
   - `filterMode: 0`
   - `enableMipMap: 0`
   - `textureType: 8`

4. 场景运行对象验证
   - `Player` 当前场景实例已读到 `player_pixel_v1.png`
   - `PixelSceneRoot` 已存在
   - `NpcSpawner` 根物体 `activeSelf = false`
   - `NpcBubbleManager` 根物体 `activeSelf = false`

## 未完成项

1. 尚未进入 Play 模式做完整运行联调
2. `CafeBackdrop` 当前仅预埋，尚未接到正式室内切换流程
3. `PlayerController` 移动时仍会用 `_movingColor` 做临时变色反馈
4. `NpcEntity` 的 `give/work` 颜色反馈仍可能在特定动作下暂时 tint 像素图

## 下次建议起点

1. 进入 Unity Play 模式，实际观察玩家/NPC尺寸是否还需要微调
2. 若小人仍偏大或偏小，可继续微调 `PixelCharacters` 的 `PPU`
3. 若希望动作状态下也完全不染色，可继续收敛 `NpcEntity` / `NpcSpawner` 的颜色反馈策略
4. 若要继续推进室内外切换，可把 `CafeBackdrop` 接到地点/场景切换逻辑
