> 设计方案: [2026-07-10_场景GameObject命名收敛_plan.md](2026-07-10_场景GameObject命名收敛_plan.md)

# 场景 GameObject 命名收敛 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

已按最新命名规则收敛 `SampleScene` 的场景对象命名，并同步调整了相关编辑器构建器 / 运行时回查字符串，避免后续再生成旧名字。

本次范围明确为：

1. `Assets/Scenes/SampleScene.scene`
2. 与场景命名直接相关的 Unity 前端脚本字符串

本次**没有批量重命名 prefab 资产内部层级**，保持与用户“先改场景”的要求一致。

## 实际改动清单

### 修改文件 (3)

- `Assets/Scenes/SampleScene.scene`
- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`
- `Assets/Scripts/Editor/DialogueUIBuilder.cs`

### 新建文档 (2)

- `docs/AIChanges/FrontendArchitecture/2026-07-10_场景GameObject命名收敛_plan.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_场景GameObject命名收敛_execution.md`

## 关键改动说明

### 1. 场景根层级命名收敛

`SampleScene` 根节点已改为新规范，例如：

- `Main Camera` → `main_camera_st`
- `GameManager` → `game_manager_st`
- `Player` → `player_dy`
- `DialogueCanvas` → `cvs_dialogue_dy`
- `PixelSceneRoot` → `go_pixel_scene_root_st`
- `SceneAnchors` → `go_scene_anchors_st`
- `EventSystem` → `event_system_st`

### 2. legacy 层级已显式标记

当前场景中停用的旧层级已统一补 `legacy` 语义：

- `SceneRoot` → `go_legacy_scene_root_st`
- `Grid_map` → `go_legacy_grid_map_st`
- `NpcSpawner` → `npc_spawner_legacy_st`
- `NpcBubbleManager` → `npc_bubble_manager_legacy_st`
- `SceneRoot` 下旧 `EventSystem` → `legacy_event_system_st`

### 3. 对话 UI 完整层级已统一

`cvs_dialogue_dy` 及其子层级已改为新规则，例如：

- `img_bg_dy`
- `img_portrait_dy`
- `txt_portrait_name_dy`
- `pnl_dialogue_dy`
- `img_dialogue_bg_st`
- `txt_speaker_name_dy`
- `txt_dialogue_dy`
- `pnl_choices_dy`
- `pnl_reply_dy`
- `txt_reply_hint_dy`
- `inp_reply_dy`
- `go_text_area_st`
- `txt_placeholder_st`
- `txt_input_dy`
- `btn_send_st`
- `txt_send_label_st`
- `btn_end_dialogue_st`
- `txt_end_dialogue_label_st`

### 4. 场景 Anchor 已统一为 `anc_..._st`

45 个场景锚点均已从原 `location_id` 形式改为：

- `anc_player_cafe_counter_st`
- `anc_street_crossroad_st`
- `anc_park_fountain_st`

这次只改了 GameObject 名称，不改 `SceneAnchor.LocationId` 数据字段，因此运行时位置解析逻辑不受影响。

### 5. 脚本字符串同步

为避免后续构建器或回查逻辑再次生成旧名字，已同步修改：

- `PortraitDialogueUI.cs`
  - `transform.Find(...)` 的回复区查找路径
- `DialogueUIBuilder.cs`
  - `GameObject.Find(...)`
  - `GetOrCreateChild(...)` 生成的场景 UI 名称
  - 新建 `EventSystem` 名称

## 验证结果

### 脚本依赖检查

- [x] 已检索脚本中与旧场景对象名相关的直接查找字符串
- [x] 已同步更新 `DialogueCanvas` 相关构建与回查路径

### 场景层级检查

已确认当前 `SampleScene` 根层级为新规范名称，且：

- `cvs_dialogue_dy` 子层级已全部统一
- `go_scene_anchors_st` 下 45 个锚点已统一
- `go_legacy_scene_root_st` / `go_legacy_grid_map_st` 已补 legacy 语义

### Unity 控制台

- [x] 当前无新增项目脚本错误
- [x] 当前仅保留既有 warning：
  - `Assets\\Scripts\\Core\\GameManager.cs(15,37): warning CS0414: 字段“GameManager._serverUrl”已被赋值，但从未使用过它的值`

## 说明

### 本次没有改 prefab 本体

虽然 `DialogueUIBuilder.cs` 已切到新命名，但这次没有继续批量改：

- `Assets/Prefabs/UI/DialogueCanvas.prefab`
- 其他 NPC / Player prefab 内部层级名

如果你下一步要继续收敛 prefab 资产命名，可以在这一轮规则和场景改名的基础上单独做，不会和当前场景结果冲突。
