> 执行记录: [2026-07-10_Unity场景与预制体规范化_execution.md](2026-07-10_Unity场景与预制体规范化_execution.md)

# Unity 场景与预制体规范化 — 设计方案

## 需求理解

用户要求按当前项目规则，统一收敛 Unity 侧现有的全部 scene 与 prefab。

这次不只处理场景层级命名，还要补齐：

1. scene 资源文件名
2. prefab 资源文件名
3. prefab 根节点与内部子层级命名
4. 会在运行时重新生成旧名字的脚本硬编码

## 规则依据

遵循：

- `docs/DesignDocs/ProjectNamingAndIndexing.md`
- `docs/DesignDocs/UnityNamingTags.md`

核心规则：

1. Unity 资源文件名优先使用 `Type_Object`
2. GameObject 使用 `<componentTag?>_<purposeTag>_<stateTag>`
3. `_` 只用于分割上述三类 tag，同一 tag 内多词使用小驼峰
4. 仅允许 `componentTag`、`purposeTag`、`stateTag` 三类 tag，不额外扩展其他 tag 类别
5. `st` 表示静态，`dy` 表示运行时会被程序改动

## 现状摘要

当前状态分成三层：

1. `SampleScene.scene` 的场景根层级已做过首轮收敛
2. `DialogueCanvas.prefab` / `ChoiceButton.prefab` 的 prefab 文件名和内部层级仍是旧名
3. `Player.prefab` 与 5 个 NPC prefab 仍混用直写名、编号名和旧子层级命名

另外，运行时代码里仍存在：

- `NPC_{npcId}`
- `ChoiceButton`
- `ChoiceLabel`

这类旧命名回写逻辑，会在 Play 模式把资产层规范冲掉。

## 本次命名目标

### Scene 资源文件

- `Assets/Scenes/SampleScene.scene` → `Assets/Scenes/Town_Main.scene`

### Prefab 资源文件

- `Assets/Prefabs/UI/DialogueCanvas.prefab` → `Assets/Prefabs/UI/UI_DialogueCanvas.prefab`
- `Assets/Prefabs/UI/ChoiceButton.prefab` → `Assets/Prefabs/UI/UI_ChoiceButton.prefab`
- `Assets/Prefabs/Player/Player.prefab` → `Assets/Prefabs/Player/Player_Main.prefab`
- `Assets/Prefabs/NPCs/01_Sakura.prefab` → `Assets/Prefabs/NPCs/Npc_Sakura.prefab`
- `Assets/Prefabs/NPCs/02_Chihaya.prefab` → `Assets/Prefabs/NPCs/Npc_Chihaya.prefab`
- `Assets/Prefabs/NPCs/03_Kazuha.prefab` → `Assets/Prefabs/NPCs/Npc_Kazuha.prefab`
- `Assets/Prefabs/NPCs/04_Tatsunosuke.prefab` → `Assets/Prefabs/NPCs/Npc_Tatsunosuke.prefab`
- `Assets/Prefabs/NPCs/05_Kujo.prefab` → `Assets/Prefabs/NPCs/Npc_Kujo.prefab`

### Prefab 根节点

- `DialogueCanvas` → `cvs_dialogue_dy`
- `ChoiceButton` → `btn_choice_st`
- `Player` → `player_dy`
- `01_Sakura` / `02_Chihaya` / ... → `npc_<npcId>_dy`

### Prefab 内部层级

#### UI Prefab

统一为现行场景规则：

- `BG_Image` → `img_bg_dy`
- `PortraitImage` → `img_portrait_dy`
- `PortraitNameLabel` → `txt_portraitName_dy`
- `DialoguePanel` → `pnl_dialogue_dy`
- `DialogueBG` → `img_dialogueBg_st`
- `SpeakerNameLabel` → `txt_speakerName_dy`
- `DialogueText` → `txt_dialogue_dy`
- `ChoicesPanel` → `pnl_choices_dy`
- `ReplyPanel` → `pnl_reply_dy`
- `ReplyHintLabel` → `txt_replyHint_dy`
- `ReplyInputField` → `inp_reply_dy`
- `TextArea` → `go_textArea_st`
- `Placeholder` → `txt_placeholder_st`
- `Text` → `txt_input_dy`
- `SendButton` → `btn_send_st`
- `EndDialogueButton` → `btn_endDialogue_st`
- `Label` → `txt_sendLabel_st` / `txt_endDialogueLabel_st`

#### Player Prefab

- `Capsule` → `spr_playerBody_dy`

#### NPC Prefab

- `cav_container` → `cvs_bubble_dy`
- `img_Bubble` → `img_bubble_dy`
- `Img_bg` → `img_bubbleBg_dy`
- `tmp_context` → `txt_bubbleContext_dy`
- `Panel` → `pnl_nameplate_dy`
- `Text (TMP)` → `txt_nameplate_dy`
- `spt_idol` → `spr_body_dy`

## 修改范围

### 代码

- `Assets/Scripts/Editor/DialogueUIBuilder.cs`
- `Assets/Scripts/NPC/NpcEntity.cs`
- `Assets/Scripts/NPC/NpcSpawner.cs`
- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`（如需同步 prefab 路径或回查名）
- 新增 Editor 批处理工具脚本

### Unity 资产

- `Assets/Scenes/Town_Main.scene`
- `Assets/Prefabs/UI/*.prefab`
- `Assets/Prefabs/Player/*.prefab`
- `Assets/Prefabs/NPCs/*.prefab`

### 文档

- 本 plan / execution
- `docs/ProjectIndex.md`
- `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-10.md`
- 其他直接引用旧路径的高频文档（按实际需要同步）

## 实施策略

### 1. 资产内部命名优先用 Unity Editor API 处理

Prefab 内部层级与场景对象名通过 Editor 脚本批量修改并保存，避免直接手改 YAML 带来的引用风险。

### 2. 资源文件名通过 AssetDatabase 重命名

优先保留 `.meta` 与 GUID，不做删除重建。

### 3. 脚本路径与运行时命名同步修正

所有使用旧 prefab 路径或旧运行时命名的代码，一并切到新规则。

### 4. 文档只同步高频入口

优先更新索引、handoff 和本轮文档；历史 execution 中保留当时真实路径，不追溯改写。

## 风险点

1. prefab 路径变更后，编辑器脚本中的 `LoadAssetAtPath(...)` 会失效
2. 运行时若继续写回 `NPC_{npcId}`，Play 模式下规范会失效
3. scene 改名后，若仍有场景路径硬编码，需要同步修正
4. `DialogueCanvas.prefab` 当前内部层级与场景实例可能不一致，需要统一收口

## 验证计划

1. Unity Console 无新增编译错误
2. `Town_Main.scene` 成为当前主场景文件
3. 全部现有 prefab 资产名改为目标规则
4. prefab 根节点与关键子节点命名符合规则
5. `DialogueUIBuilder` 重新执行后不会再生成旧文件名和旧层级名
6. NPC 运行时实例名不再回退到 `NPC_{npcId}`
