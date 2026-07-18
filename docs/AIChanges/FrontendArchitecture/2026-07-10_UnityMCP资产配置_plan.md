> 执行记录: [2026-07-10_UnityMCP资产配置_execution.md](2026-07-10_UnityMCP资产配置_execution.md)

# Unity MCP 资产配置 — 设计方案

## 需求理解

用户希望先验证 Unity MCP 是否成功连接；若连接正常，则继续帮助把近期生成的一批 Unity 美术资源配置到可直接使用的状态。

本次目标聚焦两类工作：

1. 验证 Unity Editor 与 MCP 工具链可正常通信
2. 将近期新增的立绘与像素图资源完成基础导入配置，并把 NPC 立绘数据资产切到新图

## 当前观察

- Unity MCP 已能返回 `custom-tools`、`instances`、`editor/state`、`project/info`
- 当前连接实例为 `AISc@9db8baa7dcf9cfcd`
- `Assets/Art/Generated/Portraits/*.png` 当前仍是默认 Texture 导入，不是 Sprite
- `Assets/Art/Generated/PixelCharacters/*.png` 当前仍是默认 Texture 导入，不是 Sprite
- `Assets/Art/Generated/PixelScenes/*.png` 当前仍是默认 Texture 导入，不是 Sprite
- `Assets/Data/lihun/Portrait_*.asset` 当前仍引用旧版 `Assets/Art/Sprites/Portraits/*.png`

## 方案思路

### 1. MCP 连通性验证

读取以下资源/接口作为“通过”判定：

- `mcpforunity://instances`
- `mcpforunity://editor/state`
- Unity Console

若可返回实例、场景和空闲状态，则认定连接通过。

### 2. 立绘资源配置

对 `Assets/Art/Generated/Portraits/` 下 5 张透明底立绘：

- 改为 `Sprite (2D and UI)`
- `Sprite Mode = Single`
- 开启透明支持
- 关闭 mipmaps
- 保持适合 UI 的常规过滤模式

随后把 `Assets/Data/lihun/Portrait_*.asset` 的 `Default/Happy/Sad/Surprised/Embarrassed` 全部切到对应新图，先保证默认立绘链路通。

### 3. 像素角色与地图资源配置

对 `Assets/Art/Generated/PixelCharacters/` 和 `Assets/Art/Generated/PixelScenes/`：

- 改为 `Sprite (2D and UI)`
- 关闭 mipmaps
- 使用更适合像素图的 Point 过滤
- 开启透明支持（角色图）/ 保持 Sprite 可直接进 SpriteRenderer（地图图）
- 尽量避免额外压缩带来的糊边

## 涉及文件/资产

- `Assets/Art/Generated/Portraits/` 下 5 张 PNG
- `Assets/Art/Generated/PixelCharacters/` 下 6 张 PNG
- `Assets/Art/Generated/PixelScenes/` 下 3 张 PNG
- `Assets/Data/lihun/Portrait_sakura.asset`
- `Assets/Data/lihun/Portrait_chihaya.asset`
- `Assets/Data/lihun/Portrait_kazuha.asset`
- `Assets/Data/lihun/Portrait_tatsunosuke.asset`
- `Assets/Data/lihun/Portrait_kujo.asset`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_UnityMCP资产配置_execution.md`

## 风险点

1. Unity MCP 的贴图导入设置字段名若与预期不完全一致，可能需要先小范围试配一张图再批量执行
2. PixelScenes 的 PPU 暂不做激进统一，避免影响现有场景比例；本次先做“可用导入配置”
3. `Portrait_*.asset` 统一把所有情绪先指向同一默认图，这是当前资源现状下的保守接法，不代表最终情绪差分方案
