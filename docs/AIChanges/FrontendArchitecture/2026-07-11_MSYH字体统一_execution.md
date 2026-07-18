> 设计方案: [2026-07-11_MSYH字体统一_plan.md](2026-07-11_MSYH字体统一_plan.md)

# MSYH 字体统一 — 执行记录

## 完成时间

2026-07-11

## 本次完成内容

已把 Unity 前端中关键 TMP 文本统一收口到：

- `Assets/Fonts/MSYH SDF.asset`

这轮既处理了未来新增 UI 的构建链，也处理了当前已经存在的场景 / Prefab 资产。

## 实际改动清单

### 新增脚本 (1)

1. `Assets/Scripts/Editor/TmpChineseFontNormalizer.cs`
   - 新增菜单：`Tools/Apply MSYH SDF Font`
   - 扫描当前场景中的 `TMP_Text`
   - 扫描：
     - `Assets/Prefabs/UI`
     - `Assets/Prefabs/NPCs`
   - 统一设置：
     - `font`
     - `fontSharedMaterial`

### 修改脚本 (3)

1. `Assets/Scripts/Editor/DialogueUIBuilder.cs`
   - 新建 / 更新 `UI_ChoiceButton.prefab` 时显式套用 `MSYH SDF`
   - 对话 Canvas 中所有新建 `TextMeshProUGUI` 节点显式套用 `MSYH SDF`
   - 旧的 `UI_ChoiceButton.prefab` 不再“存在即跳过”，而是可更新
2. `Assets/Scripts/Editor/StartMenuBuilder.cs`
   - 开始界面中所有新建 TMP 文本显式套用 `MSYH SDF`
3. `Assets/Scripts/Index.md`
   - 回写 `TmpChineseFontNormalizer.cs`

## Unity MCP 执行结果

通过 Unity MCP 已执行：

1. `Tools/Apply MSYH SDF Font`
2. `Tools/Build Dialogue UI`
3. `Tools/Build Start Menu`

Console 关键结果：

1. `[TmpChineseFontNormalizer] 已统一字体。Scene=12, Prefab=13`
2. `[DialogueUIBuilder] ChoiceButton 预制体已更新。`
3. `[DialogueUIBuilder] 对话 UI 构建完成。`
4. `[StartMenuBuilder] 开始界面构建完成。`

## 资产层落地结果

本轮已统一到 `MSYH SDF` 的重点对象包括：

1. `Town_Main.scene` 中开始界面与对话 UI 的 TMP 文本
2. `Assets/Prefabs/UI/UI_DialogueCanvas.prefab`
3. `Assets/Prefabs/UI/UI_ChoiceButton.prefab`
4. `Assets/Prefabs/UI/UI_StartMenuCanvas.prefab`
5. `Assets/Prefabs/UI/UI_StartMenuSaveButton.prefab`
6. `Assets/Prefabs/NPCs/*.prefab` 中名字牌相关 TMP 文本

抽样验证结果：

1. `txt_title_dy`
2. `txt_dialogue_dy`
3. `Npc_Sakura.prefab` 的 `txt_nameplate_dy`

都已切到 `Assets/Fonts/MSYH SDF.asset`。

## 脚本校验

已通过 `validate_script`：

1. `Assets/Scripts/Editor/TmpChineseFontNormalizer.cs`
2. `Assets/Scripts/Editor/DialogueUIBuilder.cs`
3. `Assets/Scripts/Editor/StartMenuBuilder.cs`

结果：

- `0 error`
- `0 warning`

## 控制台状态

在清空 Console 后重新执行字体归一化与 Builder 菜单，最终：

- 无新增 error
- 无新增 warning

说明旧的中文缺字问题已经不再继续冒出。

## 备注

在 Unity 组件实时读数里，个别 TMP 文本的 `textInfo` 缓存中仍可看到旧的占位字符历史信息，但其实际 `m_fontAsset` / `font` / `materialForRendering` 已切到 `Assets/Fonts/MSYH SDF.asset`，并且 Console 清空后未再出现缺字 warning。

## 未完成项

1. 本轮没有逐个视觉验收所有 NPC 名字牌在 Play 模式下的字号和字重
2. 若后续要做更细的中日文字体分级样式，目前还没有拆成多套主题字体

## 下次建议起点

1. 直接进 Play 模式看：
   - 开始界面标题
   - 对话面板文本
   - NPC 名字牌
2. 如果要继续做字体风格优化，优先从：
   - `Assets/Scripts/Editor/TmpChineseFontNormalizer.cs`
   - `Assets/Scripts/Editor/DialogueUIBuilder.cs`
   - `Assets/Scripts/Editor/StartMenuBuilder.cs`
   入手
