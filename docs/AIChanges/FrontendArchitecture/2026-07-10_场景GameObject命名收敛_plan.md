> 执行记录: [2026-07-10_场景GameObject命名收敛_execution.md](2026-07-10_场景GameObject命名收敛_execution.md)

# 场景 GameObject 命名收敛 — 设计方案

## 需求理解

用户要求按最新 `AGENTS.md` 中的 GameObject 命名规则，收敛 **场景对象** 的命名，不处理 prefab 资产本体。

本次目标聚焦：

1. `SampleScene` 根层级
2. `DialogueCanvas` 的完整 UI 子层级
3. 其他直接在场景中的容器与锚点对象

## 现状摘要

当前 `SampleScene` 中仍存在大量历史命名：

- PascalCase：`DialogueCanvas`、`GameManager`、`SceneRoot`
- 混合下划线与自然语言：`Shop_花時計花店`、`TMP_喫茶店(玩家)`
- 无状态后缀：`SceneAnchors`、`StreetBackdrop`
- 新补的对话 UI 虽已落回场景配置，但名字仍未按 `<component?>_<purpose>_<state>` 统一

## 规则依据

遵循：

- `docs/DesignDocs/UnityNamingTags.md`

现有可直接复用标签：

- `btn`
- `pnl`
- `txt`
- `img`
- `inp`
- `cvs`
- `anc`
- `go`
- `st`
- `dy`

本次尽量 **不新增缩写标签**，优先通过：

- 复用现有组件标签
- 或直接使用 `<purpose>_<state>`

## 修改范围

### Unity 场景

- `Assets/Scenes/SampleScene.scene`

### 文档

- `docs/AIChanges/FrontendArchitecture/2026-07-10_场景GameObject命名收敛_plan.md`
- `docs/AIChanges/FrontendArchitecture/2026-07-10_场景GameObject命名收敛_execution.md`

## 命名策略

### A. 根层级

示例方向：

- `Main Camera` → `main_camera_st`
- `GameManager` → `game_manager_st`
- `DialogueCanvas` → `cvs_dialogue_dy`
- `Player` → `player_dy`
- `SceneAnchors` → `go_scene_anchors_st`

### B. 历史停用容器标记 legacy

对当前场景里已停用的旧层级，会在 `purpose` 中显式保留 `legacy` 语义，避免和实际生效对象混淆，例如：

- `SceneRoot` → `legacy_scene_root_st`
- `Grid_map` → `legacy_grid_map_st`
- 旧 `EventSystem` 子物体 → `legacy_event_system_st`

### C. 对话 UI 层级统一

重点收敛为：

- `cvs_dialogue_dy`
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
- `btn_send_st`
- `btn_end_dialogue_st`

### D. 场景 Anchor

Anchor 子节点统一加 `anc_` 前缀与 `_st` 后缀，例如：

- `player_cafe.counter` → `anc_player_cafe_counter_st`
- `street.crossroad` → `anc_street_crossroad_st`

## 风险点

1. 某些脚本若通过 `GameObject.Find("旧名字")` 依赖场景名，会在改名后失效
2. Scene 中存在 prefab 实例和历史停用层级并存，命名时需要避免语义冲突
3. Unity 内置 `EventSystem` 若存在两个，需要区分当前有效与 legacy 残留

## 处理策略

1. 先全局搜索脚本中是否存在对这些旧名字的直接查找
2. 若无字符串依赖，直接用 Unity MCP / Editor 代码批量改名
3. 改名后再跑一次 Console 检查，确认没有新增异常

## 验证计划

1. 搜索确认没有依赖旧场景名的硬编码查找
2. `SampleScene` 中目标对象已按规则改名
3. `DialogueCanvas` 完整层级已统一为新规则
4. Unity Console 无新增项目脚本错误
