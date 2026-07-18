# 项目命名与索引规范

## 目的

本规范用于统一项目中的命名与文件索引规则，减少跨端协作时的歧义，并为后续新增资产、配置、脚本和文档提供稳定入口。

## 1. 跨端共享 ID 规则

适用对象：

- NPC ID
- 地点 ID
- 行为 ID
- 物品 ID
- 事件 ID
- 共享配置键
- 需要在 Unity / Python / JSON / 存档 / 数据库之间稳定传递的标识符

统一要求：

1. 一律使用 `snake_case`
2. 只使用英文小写、数字和下划线
3. 不使用空格、中文、连字符或随意缩写
4. 一旦进入共享配置、协议、存档或数据库，默认视为稳定主键，不轻易改名

示例：

- `flower_shop_front`
- `talk_about_rain`
- `river_stone`
- `npc_sakura`

## 2. 显示名与程序 ID 分离

所有面向玩家展示的文本，必须与程序内部 ID 分离。

正确做法：

- `id: flower_shop`
- `display_name: 花時計花店`

不要把：

- 中文显示名
- 版本性描述
- 临时策划备注

直接塞进程序 ID。

## 3. Python 命名规则

遵循 Python 社区常规习惯：

- 文件名：`snake_case.py`
- 函数名：`snake_case`
- 变量名：`snake_case`
- 类名：`PascalCase`
- 常量名：`UPPER_SNAKE_CASE`

示例：

- `behavior_engine.py`
- `build_npc_to_npc_prompt()`
- `NpcDialogueManager`
- `DEFAULT_ROUTINES`

## 4. Unity C# 命名规则

遵循 C# / Unity 常规习惯：

- 文件名：与主类同名，使用 `PascalCase`
- 类名：`PascalCase`
- 公有属性 / 公有方法：`PascalCase`
- 私有字段：项目内沿用当前代码风格，可使用 `_camelCase`
- 局部变量与参数：`camelCase`

示例：

- `PortraitDialogueUI.cs`
- `SceneAnchorRegistry.cs`
- `TryResolveNearestLocation(...)`
- `_replyPanel`

## 5. Unity 资源文件命名规则

Unity 资源文件名与运行时 `GameObject` 命名分开管理。

资源文件名重点表达：

- 资源类型
- 业务对象
- 必要时的版本或用途

推荐格式：

- `Type_Object`
- `Type_Object_Variant`
- `Type_Object_v1`

示例：

- `UI_DialogueCanvas.prefab`
- `UI_ChoiceButton.prefab`
- `Npc_Sakura.prefab`
- `Town_Main.unity`
- `Test_Dialogue.unity`
- `NpcScheduleConfig.asset`

不要求把 `st / dy` 这类运行时状态标签写进资源文件名。

## 6. GameObject 命名规则

适用对象：

- 场景中的运行时层级对象
- Prefab 根节点
- Prefab 内子节点
- UI 层级节点

统一格式：

- `<componentTag?>_<purposeTag>_<stateTag>`

字段说明：

- `componentTag`：主要组件英文缩写，可为空
- `purposeTag`：对象用途，单词组合时使用小驼峰
- `stateTag`：对象是否会被程序修改的状态标签

若没有明确组件前缀，则直接使用：

- `<purposeTag>_<stateTag>`

`_` 只用于分割上述三类 tag，不在同一 tag 内继续拆词。
如果 `componentTag` 或 `purposeTag` 内部需要多个单词，使用小驼峰。
除 `componentTag`、`purposeTag`、`stateTag` 外，不新增其他类别的 tag。

状态标签固定为：

- `st`：static，不会被程序修改
- `dy`：dynamic，会被程序修改

示例：

- `btn_cancel_st`
- `pnl_dialogue_dy`
- `txt_speakerName_dy`
- `spr_playerBody_dy`
- `anc_riverBank_st`

执行要求：

1. 新建场景、Prefab 与 UI 层级对象时，优先遵守本格式
2. 创建前优先复用已有标签，不重复造同义缩写
3. 若需要新增标签，先补到 `docs/DesignDocs/UnityNamingTags.md`，再投入使用
4. 历史对象可暂时并存；若要统一清理，应单独开一轮命名收敛

标签参考表见：

- `docs/DesignDocs/UnityNamingTags.md`

## 7. 核心文件索引规则

不是所有文件都要进索引，只要求以下“核心文件”回写索引：

- 关键入口脚本
- 跨模块共享配置
- 关键设计文档
- 高频协作资产
- 会被后续会话反复引用的文件

新增上述文件后，应回写对应索引文档，至少写明：

1. 文件路径
2. 作用
3. 谁会改它
4. 何时优先查看

## 8. 功能目录与索引规则

项目自维护目录按功能划分，不按日期、会话、人员或“最新状态”划分。

目录说明规则：

1. 每个受维护功能目录使用 `README.md` 说明文件夹功能、文件夹内容和进一步入口。
2. 如果目录已有详细 `Index.md`，README 负责目录概览并指向 Index；Index 负责核心文件定位。
3. `docs/ProjectIndex.md` 是跨目录总入口，只登记功能域和主入口，不维护按时间排序的文件清单。
4. 普通叶子文件通过目录 README、Index 或 `rg` 定位，不强制进入总索引。
5. Unity 生成目录、第三方包、缓存、日志和纯素材叶子目录不机械添加 README。

执行证据规则：

1. `docs/AIChanges/<功能域>/` 保存对应功能的 plan / execution。
2. 日期可保留在执行证据文件名中用于审计，不得作为目录或索引分类。
3. 跨功能记录只保存一份，按主要变更目标选择目录，其他功能入口通过引用关联。
4. handoff 只进入 `docs/AIChanges/Archive/Handoffs/`，不作为默认查找入口。
5. 新增功能目录时必须同步回写上级 README 和必要的总索引。

## 9. 执行原则

1. 新增内容优先遵守本规范
2. 旧内容若暂未迁移，可先与新规范并存，但不得继续新增同类时间目录或根层记录
3. 若需要新增缩写、例外命名或新的索引入口，应先补文档，再落实际内容
4. 若未来要清理历史命名债，建议单独开一轮变更，不与业务开发混做

## 10. Unity 相关规范入口

本文件只承载“命名与索引”规则，不继续堆放 Unity MCP 资产层细则。

Unity 侧以下内容统一改看：

- `docs/DesignDocs/UnityNamingTags.md`
  - 负责 GameObject / Prefab / UI 层级标签参考
- `docs/DesignDocs/UnityMCPUsageRules.md`
  - 负责 Unity MCP 使用规范、资产层 / 运行时边界、默认约定与例外规则

后续若继续新增 Unity 场景、Prefab、UI、TMP 字体、SerializeField 连线等建议，优先追加到 `UnityMCPUsageRules.md`，不要再回写到本文件。
