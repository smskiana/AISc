> 执行记录: [2026-07-10_Unity像素场景与小人首批补图_execution.md](2026-07-10_Unity像素场景与小人首批补图_execution.md)

# Unity 像素场景与小人首批补图 — 方案

## 需求理解

当前项目已经有：

1. 对话 UI 的立绘方向
2. 场景结构与地图设计文档
3. 世界内 NPC / 玩家行走逻辑

但 Unity 场景侧仍主要依赖占位图和纯色方块，因此需要先补一批“可用于世界内演示”的像素风资源。

用户本轮需求聚焦两类资源：

1. 场景图
2. 在场景内移动的小人图

并且明确要求这些资源采用像素风格。

## 本次范围

本次先交付“第一批像素资产”，优先让商店街原型具备统一视觉语言：

### 场景图

1. 商店街主街像素场景
2. 玩家喫茶店内部像素场景

### 小人图

1. 玩家
2. 鹿岛樱
3. 千早
4. 和叶
5. 龙之介
6. 九条莲

## 方案思路

### 1. 资源定位

本批次资源优先作为：

- Unity 原型中的替代占位图
- 风格定锚图
- 后续继续扩展 walk cycle / tilemap / 差分动作时的基准

### 2. 场景图策略

场景图采用：

- 日式治愈系小镇像素风
- 类 16-bit / 高级像素插画感
- 不是纯写实 tile set，而是适合当前原型快速替换的整张场景图

优先出：

1. 商店街主街
2. 玩家喫茶店内部

这样能先覆盖：

- 世界内漫游主场景
- 关键对话/驻留空间

### 3. 小人图策略

考虑当前生成稳定性与本轮交付效率，本次先产出“透明底单人像素角色图”而不是复杂 walk spritesheet。

原因：

1. 先把世界内角色视觉从彩色方块升级为真正角色
2. 单角色透明图更容易直接替换当前占位 `char_*.png`
3. 多方向 walk cycle 可以基于同一风格继续第二批补图

本次默认采用：

- 像素风 chibi / SD 比例
- 单角色
- 透明底 `PNG`
- 朝向以“正面或轻微三分之四朝向、适合场景内小人使用”为主

### 4. 输出目录

本次不覆盖旧资源，先落到新目录：

- `Assets/Art/Generated/PixelScenes/`
- `Assets/Art/Generated/PixelCharacters/`

### 5. 文件命名

场景图：

- `street_arcade_pixel_v1.png`
- `player_cafe_interior_pixel_v1.png`

小人图：

- `player_pixel_v1.png`
- `sakura_pixel_v1.png`
- `chihaya_pixel_v1.png`
- `kazuha_pixel_v1.png`
- `tatsunosuke_pixel_v1.png`
- `kujo_pixel_v1.png`

## 涉及文件

### 新建文档

- `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity像素场景与小人首批补图_plan.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity像素场景与小人首批补图_execution.md`

### 新增资源

- `Assets/Art/Generated/PixelScenes/*.png`
- `Assets/Art/Generated/PixelCharacters/*.png`

## 风险点

1. 像素角色尺寸可能与最终 Unity 导入规格不完全一致
   - 当前先保证风格和透明底正确
   - 后续可再做统一画布与 import setting 调整

2. 单张像素角色图不等于完整 walking spritesheet
   - 本批次优先完成“角色替代占位图”
   - 第二批可继续补 4 向待机/行走帧

3. 场景图当前更偏整图背景而非可拼 tile set
   - 适合快速替换现有演示原型
   - 若后续要真正大规模搭建 tilemap，可再拆为 tile set 生产流程

## 验证方式

1. 检查所有角色图是否为透明底 `RGBA`
2. 检查场景图尺寸是否适合作为原型背景图
3. 人工确认像素风是否统一
4. 确认目录结构稳定，便于后续接入 Unity
