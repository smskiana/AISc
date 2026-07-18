> 执行记录: [2026-07-10_Unity立绘透明底首批补图_execution.md](2026-07-10_Unity立绘透明底首批补图_execution.md)

# Unity 立绘透明底首批补图 — 方案

## 需求理解

当前 Unity 前端已经具备对话立绘显示能力，但 `Assets/Art/Sprites/Portraits/` 下现有角色图基本仍是占位资源，无法支撑正式对话表现。

本次目标是先补齐一批可直接用于 Unity 的角色默认立绘，并且统一满足：

1. 人物图为透明底 `PNG`
2. 风格与《樱桥通》的治愈日常气质一致
3. 立绘适配 `PortraitDialogueUI` 的对话使用场景
4. 非破坏式落盘，先放到新目录，避免覆盖旧占位资源

## 本次范围

本批次先处理 5 位核心 NPC 的默认立绘：

1. 鹿岛樱
2. 千早
3. 和叶
4. 龙之介
5. 九条莲

其中鹿岛樱先作为风格样例，剩余 4 位继续沿同一画风与规格推进。

## 方案思路

### 1. 生成方式

使用内建图像生成工具先产出“纯色绿底人物图”，再通过本地抠底脚本移除背景，输出透明底成品。

这样做的原因：

1. 当前默认图像生成链路更适合先出稳定角色形象
2. 项目需要的是 Unity 可直接叠加的透明立绘
3. 纯色抠底流程能保留发丝等边缘细节，并避免把背景混进人物图

### 2. 视觉方向

统一采用：

- 二次元治愈日常风
- 干净线稿 + 柔和赛璐璐/轻薄涂层阴影
- 适合视觉小说 / 对话 UI 的半身到中近景立绘
- 单角色、无道具遮挡主体、背景完全可抠除

同时根据各角色 Profile 保留差异化特征：

- 千早：活力短发、运动头带、面包店二代目的朝气
- 和叶：文艺推理气质、圆框眼镜、旧书店店主的安静感
- 龙之介：社恐宅系、耳机、缩起来的站姿
- 九条莲：颓废警官、大叔感、松垮制服与疲惫但可靠的气场

### 3. 文件落盘策略

不覆盖现有占位资源，先输出到：

`Assets/Art/Generated/Portraits/`

命名规则：

- `sakura_default_transparent_v1.png`
- `chihaya_default_transparent_v1.png`
- `kazuha_default_transparent_v1.png`
- `tatsunosuke_default_transparent_v1.png`
- `kujo_default_transparent_v1.png`

## 涉及文件

### 新建文档

- `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity立绘透明底首批补图_plan.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity立绘透明底首批补图_execution.md`

### 新增资源

- `Assets/Art/Generated/Portraits/*.png`

## 风险点

1. 角色一致性风险
   - 多张图若分别生成，容易出现线条与光影不完全统一
   - 处理方式：统一 prompt 结构、镜头规格、渲染语言与项目气质

2. 抠边风险
   - 发丝边缘可能残留绿边
   - 处理方式：使用本地 `remove_chroma_key.py`，开启 `soft-matte` 与 `despill`

3. 与现有 ScriptableObject 未自动接线
   - 本次先交付资源，不直接改现有 `Portrait_*.asset`
   - 后续如需要，可再做第二步资源挂接

## 验证方式

1. 检查输出文件是否为 `RGBA`
2. 检查四角 alpha 是否为 `0`
3. 人工查看发丝、肩部、服装边缘是否有明显绿边
4. 确认资源目录与命名稳定，便于 Unity 后续接入
