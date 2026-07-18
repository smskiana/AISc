> 设计方案: [2026-07-10_Unity立绘透明底首批补图_plan.md](2026-07-10_Unity立绘透明底首批补图_plan.md)

# Unity 立绘透明底首批补图 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已完成《樱桥通》Unity 前端首批 5 位核心 NPC 默认立绘资源补图，并全部输出为可直接用于对话 UI 的透明底 `PNG`。

## 实际改动清单

### 新建文档 (2)

| 文件 | 说明 |
|------|------|
| `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity立绘透明底首批补图_plan.md` | 本次补图方案 |
| `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity立绘透明底首批补图_execution.md` | 本执行记录 |

### 新增资源 (5)

| 文件 | 说明 |
|------|------|
| `Assets/Art/Generated/Portraits/sakura_default_transparent_v1.png` | 鹿岛樱默认立绘透明底成品 |
| `Assets/Art/Generated/Portraits/chihaya_default_transparent_v1.png` | 千早默认立绘透明底成品 |
| `Assets/Art/Generated/Portraits/kazuha_default_transparent_v1.png` | 和叶默认立绘透明底成品 |
| `Assets/Art/Generated/Portraits/tatsunosuke_default_transparent_v1.png` | 龙之介默认立绘透明底成品 |
| `Assets/Art/Generated/Portraits/kujo_default_transparent_v1.png` | 九条莲默认立绘透明底成品 |

## 执行方式

### 1. 角色设定对齐

生成前先阅读以下角色设定，确保立绘不只“像二次元角色”，而是尽量贴近项目内人物：

- `docs/DesignDocs/CharacterProfiles/02_Chihaya.md`
- `docs/DesignDocs/CharacterProfiles/03_Kazuha.md`
- `docs/DesignDocs/CharacterProfiles/04_Tatsunosuke.md`
- `docs/DesignDocs/CharacterProfiles/05_Kujo.md`

### 2. 生成流程

统一采用两段式流程：

1. 图像生成：输出纯绿底角色源图
2. 本地处理：使用 `remove_chroma_key.py` 去底，导出透明底 `PNG`

这样做的结果是：

- Unity 可直接使用
- 发丝和衣物边缘保留较自然
- 不会把背景一并烘进人物图

### 3. 资源目录

本次没有覆盖旧占位资源，而是新建目录：

`Assets/Art/Generated/Portraits/`

这样后续可以先人工挑图、再决定是否接到 `Portrait_*.asset`。

## 验证结果

### 已完成验证

- [x] 5 张成品文件均已生成到项目目录
- [x] 5 张成品均为 `RGBA`
- [x] 5 张成品四角 alpha 均为 `0`
- [x] 已人工查看透明边缘，无明显大块绿底残留

### 输出尺寸

| 文件 | 尺寸 |
|------|------|
| `sakura_default_transparent_v1.png` | `1024x1536` |
| `chihaya_default_transparent_v1.png` | `1024x1536` |
| `kazuha_default_transparent_v1.png` | `1024x1536` |
| `tatsunosuke_default_transparent_v1.png` | `1024x1536` |
| `kujo_default_transparent_v1.png` | `1023x1537` |

## 说明

1. 九条莲这张不是标准 `1024x1536`
   - 当前透明图本身可用
   - 如后续 UI 需要统一尺寸，可以再做一轮无损画布对齐

2. 本次只交付资源，不改现有 `Portrait_*.asset`
   - 这样能避免在未挑定最终版本前直接覆盖现有引用

3. 当前属于“第一版默认立绘”
   - 后续还可以继续补：
   - 情绪差分（开心 / 低落 / 惊讶 / 害羞）
   - 玩家立绘
   - 统一背景图风格

## 下次建议起点

1. 将这 5 张图接到现有 `NpcPortraitData` 资产
2. 在 Unity `PortraitDialogueUI` 里实测裁切与显示比例
3. 若显示过满，补一轮统一留白版或统一尺寸版
