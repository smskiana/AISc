# Unity 命名标签参考

## 适用范围

本表用于 Unity 场景、Prefab、UI 层级中 **新建 GameObject** 的命名约束。

统一格式：

- `<componentTag?>_<purposeTag>_<stateTag>`

说明：

- `componentTag`：主要组件英文缩写，可为空
- `purposeTag`：对象用途，单词组合时使用小驼峰
- `stateTag`：对象是否会被程序修改的状态标签

若没有明确组件前缀，则直接写：

- `<purposeTag>_<stateTag>`

`_` 只用于分割 `componentTag` / `purposeTag` / `stateTag` 三类 tag。
同一 tag 内部如果需要多个单词，统一使用小驼峰，不再继续用 `_` 拆分。
除这三类 tag 外，不新增其他类别的 tag。

示例：

- `btn_cancel_st`
- `pnl_dialogue_dy`
- `txt_speakerName_dy`
- `spr_playerBody_dy`
- `anc_riverBank_st`

## 状态标签

| 标签 | 含义 | 说明 |
|------|------|------|
| `st` | static | 运行时不会被程序主动修改名称、内容、显隐、层级、位置或配置状态 |
| `dy` | dynamic | 运行时会被程序主动修改内容、显隐、层级、位置、挂载表现或相关配置状态 |

## 常用组件标签

| 标签 | 含义 |
|------|------|
| `btn` | Button |
| `pnl` | Panel |
| `txt` | Text / TMP_Text |
| `img` | Image |
| `inp` | InputField / TMP_InputField |
| `spr` | Sprite / SpriteRenderer |
| `cvs` | Canvas |
| `anc` | Anchor |
| `go` | 通用空物体 / 通用容器 |

## 使用规则

1. 优先复用本表已存在标签，不重复造同义缩写。
2. 新增标签前，先检查项目文档和现有 Unity 资产是否已有更合适写法。
3. 若确需新增标签，必须先补进本表，再在场景或 prefab 中使用。
4. 本表记录的是 `componentTag` 候选值，不是完整对象名；完整命名仍应按三段格式组合。

## 备注

当前项目中已有一部分历史对象名仍使用 `DialogueCanvas`、`ReplyPanel`、`SendButton` 这类直写形式。
本表优先约束后续新建对象；若未来要统一清理历史命名，请单独开变更并配合 Unity 引用校验处理。
