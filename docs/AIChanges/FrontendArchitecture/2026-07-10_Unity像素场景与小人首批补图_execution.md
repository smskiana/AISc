> 设计方案: [2026-07-10_Unity像素场景与小人首批补图_plan.md](2026-07-10_Unity像素场景与小人首批补图_plan.md)

# Unity 像素场景与小人首批补图 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已完成一批可直接用于 Unity 原型替换的像素风资源，包括：

1. 俯视角地图风格场景图
2. 场景内使用的顶视角像素小人透明图

同时，本次中途生成过一张“偏宣传图 / 背景图”的街道图，但在用户反馈后已经切换到真正适合地图使用的俯视角方向。

## 实际改动清单

### 新建文档 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity像素场景与小人首批补图_plan.md` | 本次补图方案 |
| `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity像素场景与小人首批补图_execution.md` | 本执行记录 |

### 新增目录 (2)

| 目录 | 说明 |
|------|------|
| `Assets/Art/Generated/PixelScenes/` | 像素场景图输出目录 |
| `Assets/Art/Generated/PixelCharacters/` | 像素小人图输出目录 |

### 新增资源：像素场景图

| 文件 | 说明 | 状态 |
|------|------|------|
| `Assets/Art/Generated/PixelScenes/street_topdown_map_v1.png` | 商店街主街俯视角地图图 | ✅ 推荐使用 |
| `Assets/Art/Generated/PixelScenes/player_cafe_topdown_map_v1.png` | 玩家喫茶店内部俯视角地图图 | ✅ 推荐使用 |
| `Assets/Art/Generated/PixelScenes/street_arcade_pixel_v1.png` | 第一版商店街像素街景图 | ⚠️ 更像背景宣传图，不建议直接当地图 |

### 新增资源：像素小人图

| 文件 | 说明 |
|------|------|
| `Assets/Art/Generated/PixelCharacters/player_pixel_v1.png` | 玩家顶视角像素小人 |
| `Assets/Art/Generated/PixelCharacters/sakura_pixel_v1.png` | 鹿岛樱顶视角像素小人 |
| `Assets/Art/Generated/PixelCharacters/chihaya_pixel_v1.png` | 千早顶视角像素小人 |
| `Assets/Art/Generated/PixelCharacters/kazuha_pixel_v1.png` | 和叶顶视角像素小人 |
| `Assets/Art/Generated/PixelCharacters/tatsunosuke_pixel_v1.png` | 龙之介顶视角像素小人 |
| `Assets/Art/Generated/PixelCharacters/kujo_pixel_v1.png` | 九条莲顶视角像素小人 |

## 执行过程说明

### 1. 先尝试了“像素街景背景图”方向

最初生成了：

- `street_arcade_pixel_v1.png`

该图虽然是像素风，但更偏“世界观背景图 / 宣传场景图”，不适合作为真正可读的游戏地图。

用户随后明确指出：

- 需要的是类似 `Assets/Sprites/Map/kenney_roguelike-rpg-pack/Sample1.png` 的俯视角地图

因此后续路线已切换。

### 2. 改为真正的俯视角地图生成

参考用户给出的 `Sample1.png` 后，重新生成：

1. `street_topdown_map_v1.png`
2. `player_cafe_topdown_map_v1.png`

这两张图的目标是：

- 从“可当地图使用”的角度出发
- 维持清晰的 walkable / blocked 可读性
- 保持日式治愈像素风氛围

### 3. 小人图采用透明底流程

为保证 Unity 可直接替换占位角色图，本次小人图统一采用：

1. 生成纯洋红底像素角色源图
2. 使用本地 `remove_chroma_key.py` 去底
3. 输出透明底 `PNG`

## 验证结果

### 已完成验证

- [x] `PixelScenes` 目录下场景图已生成
- [x] `PixelCharacters` 目录下 6 张小人图已生成
- [x] 6 张小人图均为 `RGBA`
- [x] 6 张小人图四角 alpha 均为 `0`
- [x] 俯视角主街图与喫茶店内部图已人工检查，方向正确，属于地图视角而非背景立绘

### 文件规格

#### 小人图

| 文件 | 尺寸 | 模式 |
|------|------|------|
| `player_pixel_v1.png` | `1254x1254` | `RGBA` |
| `sakura_pixel_v1.png` | `1254x1254` | `RGBA` |
| `chihaya_pixel_v1.png` | `1254x1254` | `RGBA` |
| `kazuha_pixel_v1.png` | `1254x1254` | `RGBA` |
| `tatsunosuke_pixel_v1.png` | `1254x1254` | `RGBA` |
| `kujo_pixel_v1.png` | `1254x1254` | `RGBA` |

#### 场景图

| 文件 | 尺寸 | 模式 |
|------|------|------|
| `street_topdown_map_v1.png` | `1536x1024` | `RGB` |
| `player_cafe_topdown_map_v1.png` | `1448x1086` | `RGB` |
| `street_arcade_pixel_v1.png` | `1586x992` | `RGB` |

## 当前限制

1. 小人图目前是“单张顶视角角色图”
   - 还不是 4 向行走 spritesheet
   - 适合先替换现有占位角色显示

2. 地图图目前是“整张顶视角地图图”
   - 还不是可无限拼接的 tile set
   - 适合原型阶段快速替换和定视觉方向

3. 第一版主街街景图仍保留
   - 方便后续做宣传背景或对话背景时参考
   - 但不建议直接拿来做地图

## 下次建议起点

1. 继续补：
   - `park_topdown_map_v1.png`
   - `riverside_topdown_map_v1.png`
   - 其他店铺内部俯视角图

2. 小人下一步建议改做：
   - 4 向待机图
   - 4 向 walk cycle spritesheet

3. 若要真正接进 Unity：
   - 统一小人图画布尺寸
   - 统一 Pixels Per Unit
   - 设置 Sprite Mode / Filter Mode / Compression
