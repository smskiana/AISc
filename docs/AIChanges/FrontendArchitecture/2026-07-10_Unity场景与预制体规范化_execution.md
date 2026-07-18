> 设计方案: [2026-07-10_Unity场景与预制体规范化_plan.md](2026-07-10_Unity场景与预制体规范化_plan.md)

# Unity 场景与预制体规范化 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已按用户最新确认，将 Unity GameObject 命名规范同步为固定三类 tag：

- `componentTag`
- `purposeTag`
- `stateTag`

新规则要求 `_` 只用于分割上述 tag；同一 tag 内多词使用小驼峰，例如：

- `spr_playerBody_dy`
- `txt_speakerName_dy`
- `anc_playerCafeCounter_st`

本轮已完成规范文档、生成脚本、Editor 规范化工具，并已实际执行 Unity 资产批处理。

## 实际改动清单

### 修改文档

- `docs/DesignDocs/ProjectNamingAndIndexing.md`
- `docs/DesignDocs/UnityNamingTags.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_Unity场景与预制体规范化_plan.md`
- `Assets/Scripts/Index.md`

### 修改脚本

- `Assets/Scripts/Editor/DialogueUIBuilder.cs`
- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`
- `Assets/Scripts/NPC/NpcEntity.cs`
- `Assets/Scripts/NPC/NpcSpawner.cs`

### 新增脚本

- `Assets/Scripts/Editor/UnityNamingNormalizer.cs`

### 修改 Unity 资产

- `Assets/Scenes/Town_Main.scene`
- `Assets/Prefabs/UI/UI_DialogueCanvas.prefab`
- `Assets/Prefabs/UI/UI_ChoiceButton.prefab`
- `Assets/Prefabs/Player/Player_Main.prefab`
- `Assets/Prefabs/NPCs/Npc_Sakura.prefab`
- `Assets/Prefabs/NPCs/Npc_Chihaya.prefab`
- `Assets/Prefabs/NPCs/Npc_Kazuha.prefab`
- `Assets/Prefabs/NPCs/Npc_Tatsunosuke.prefab`
- `Assets/Prefabs/NPCs/Npc_Kujo.prefab`

## 关键改动说明

### 1. 命名规范已改为三类 tag

已明确写入：

- 格式：`<componentTag?>_<purposeTag>_<stateTag>`
- `componentTag` 可为空
- `purposeTag` 多词时使用小驼峰
- `stateTag` 仍固定为 `st` / `dy`
- 不新增其他 tag 类别

### 2. 对话 UI 生成器已切到新命名

`DialogueUIBuilder` 后续会生成：

- `txt_portraitName_dy`
- `img_dialogueBg_st`
- `txt_speakerName_dy`
- `txt_replyHint_dy`
- `go_textArea_st`
- `btn_endDialogue_st`
- `txt_endDialogueLabel_st`
- `txt_choiceLabel_st`

同时 prefab 路径已切到：

- `Assets/Prefabs/UI/UI_DialogueCanvas.prefab`
- `Assets/Prefabs/UI/UI_ChoiceButton.prefab`

### 3. 对话 UI 运行时回查路径已同步

`PortraitDialogueUI` 中回复区回查已同步为：

- `txt_replyHint_dy`
- `btn_endDialogue_st`

### 4. NPC 运行时命名已同步

`NpcEntity` 与 `NpcSpawner` 不再写回旧的 `NPC_{npcId}`。

现在运行时实例名会构造成：

- `npc_sakura_dy`
- `npc_chihaya_dy`

若未来 `npcId` 包含下划线，也会先转成小驼峰 purposeTag，例如：

- `some_npc_id` → `npc_someNpcId_dy`

### 5. 新增一次性 Editor 规范化工具

新增菜单：

- `Tools/Normalize Unity Scene And Prefabs`

工具已处理：

- scene 资源名：`SampleScene.scene` → `Town_Main.scene`
- UI prefab 资源名：`DialogueCanvas.prefab` → `UI_DialogueCanvas.prefab`
- UI prefab 资源名：`ChoiceButton.prefab` → `UI_ChoiceButton.prefab`
- Player prefab 资源名：`Player.prefab` → `Player_Main.prefab`
- NPC prefab 资源名：`01_Sakura.prefab` 等 → `Npc_Sakura.prefab` 等
- prefab 根节点与内部子层级名
- scene 内已符合旧 snake 风格的对象名通用转小驼峰 purposeTag
- prefab 根 `m_Name` 已额外写回 YAML，避免 Unity 主资产名行为把根名保留为资源文件名

## 验证结果

### 已完成

- [x] 静态搜索确认旧 UI 生成名不再出现在生成逻辑中
- [x] 旧命名字符串仅保留在 `UnityNamingNormalizer` 的旧名映射中
- [x] 规范文档已写入三类 tag 规则
- [x] 新增 Editor 工具已写入 `Assets/Scripts/Index.md`
- [x] 已执行 Unity 菜单 `Tools/Normalize Unity Scene And Prefabs`
- [x] 当前活动场景已变为 `Assets/Scenes/Town_Main.scene`
- [x] scene / prefab 资源文件名已实际落盘
- [x] prefab 根 `m_Name` 已写入新命名，例如 `cvs_dialogue_dy`、`npc_sakura_dy`
- [x] Unity Console 当前无 error

## 验证备注

Unity MCP 的 `manage_prefabs(get_hierarchy)` 对 prefab root 的显示仍按资源文件名展示，例如 `UI_DialogueCanvas`。

已用文件本体检查确认 YAML 中根 `m_Name` 为：

- `cvs_dialogue_dy`
- `btn_choice_st`
- `player_dy`
- `npc_sakura_dy`
- `npc_chihaya_dy`
- `npc_kazuha_dy`
- `npc_tatsunosuke_dy`
- `npc_kujo_dy`

## 后续建议

1. 下一步可做一次 Unity Play 模式烟测，确认 prefab 路径更新后 NPC 生成与对话 UI 引用仍正常。
2. 若后续继续执行 `Tools/Normalize Unity Scene And Prefabs`，当前工具已包含 prefab 根 `m_Name` 的落盘修正。
