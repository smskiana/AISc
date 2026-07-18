> 执行记录: [2026-07-12_Unity像素地图第二批补图_execution.md](2026-07-12_Unity像素地图第二批补图_execution.md)

# Unity 像素地图第二批补图 — 方案

## 需求理解

本轮需要参考 `docs/DesignDocs/MapDesign.md` 与已生成的 `Assets/Art/Generated/PixelScenes/` 资源，继续补齐樱桥通地图原型中缺失的像素场景图：

1. 樱桥 / 河边樱花道相关地图
2. 河边小公园地图
3. 除玩家喫茶店以外的全部建筑内部地图

现有 `street_topdown_map_v1.png` 和 `player_cafe_topdown_map_v1.png` 已经确立了当前方向：俯视角、温暖日式小镇像素图、整图地图资源，而不是正式 tile set。

## 本次范围

### 新增像素场景图

- `Assets/Art/Generated/PixelScenes/riverside_bridge_topdown_map_v1.png`
- `Assets/Art/Generated/PixelScenes/park_topdown_map_v1.png`
- `Assets/Art/Generated/PixelScenes/flower_shop_topdown_map_v1.png`
- `Assets/Art/Generated/PixelScenes/bakery_topdown_map_v1.png`
- `Assets/Art/Generated/PixelScenes/bookstore_topdown_map_v1.png`
- `Assets/Art/Generated/PixelScenes/wagashi_topdown_map_v1.png`
- `Assets/Art/Generated/PixelScenes/police_box_topdown_map_v1.png`

### 不在本轮处理

- 不拆 tile set
- 不接入 Unity 场景或 Prefab
- 不调整 Sprite Import Settings
- 不生成四季 / 昼夜差分
- 不修改共享地点 ID 或后端感知配置

## 方案思路

1. 继续使用整张俯视角地图图，优先服务原型替换和视觉定锚。
2. 室内图参考 `player_cafe_topdown_map_v1.png` 的画幅感：房间墙体清晰、可行走区域明确、家具阻挡关系可读。
3. 室外图参考 `street_topdown_map_v1.png` 的自然材质和建筑密度：石板路、草地、樱花、木栅栏、水面与桥面需要读起来像可探索区域。
4. 文件命名使用稳定 `snake_case`，沿用 `*_topdown_map_v1.png`。
5. 本轮只新增资源与执行记录，避免影响现有可运行状态。

## 设计要点摘录

### 樱桥 / 河边樱花道

- 沿河碎石小径
- 河岸樱花树列
- 旧石拱桥，桥栏刻有「樱桥」
- 河边长椅
- 夕阳感可作为氛围，但地图可读性优先

### 河边小公园

- 中央大樱花树
- 小喷泉
- 两张长椅
- 草地和入口坡道
- 与主街东尽头、河边樱花道的连接关系清晰

### 店铺内部

- 花店：工作台、橱窗展示、柜台、后台私人空间，花和绿植最丰富
- 面包店：烤炉区、揉面台、展示架、柜台，暖橙色和面包陈列突出
- 旧书店：推理区、文学区、旧沙发、窗边座、柜台，走道狭窄但可读
- 和果子店：展示柜、柜台、后台工作台、传统木质格子风格
- 派出所：办公桌、靠窗椅、拼图角，小而干净，门外猫/长椅元素可弱提示

## 风险点

1. AI 生成图可能出现不可控文字；提示中会要求避免大段可读文字，仅保留极少招牌感元素。
2. 生成图仍是整图资产，不等同于可碰撞 tile map；后续接入时仍需独立 Collider/Anchor 配置。
3. 店铺比例可能和文档 tile 数不完全一致；本轮优先保证视觉功能区完整和原型可用。

## 验证方式

1. 检查目标 PNG 均已落到 `Assets/Art/Generated/PixelScenes/`。
2. 检查图片尺寸、格式可被 Unity 读取。
3. 人工查看每张图是否为俯视角地图，而不是宣传背景图。
4. 确认不覆盖既有资源。
