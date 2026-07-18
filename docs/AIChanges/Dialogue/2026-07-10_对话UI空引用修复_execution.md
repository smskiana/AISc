> 设计方案: 本次为单文件小修，未单独建立 plan 文档。

# 对话 UI 空引用修复 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

修复了点击 NPC 开始对话时 `PortraitDialogueUI` 抛出 `NullReferenceException` 的问题。

异常根因不是 NPC 或 `GameManager` 本身为空，而是场景中的 `DialogueCanvas` 初始处于隐藏状态，导致 `PortraitDialogueUI` 在首次被 `GameManager.StartDialogue()` 直接调用时，其内部 `_portraitMap` 尚未完成初始化。

## 实际改动清单

### 修改脚本 (1)

- `Assets/Scripts/Dialogue/PortraitDialogueUI.cs`

### 新建文档 (1)

- `docs/AIChanges/Dialogue/2026-07-10_对话UI空引用修复_execution.md`

## 实现细节

### 1. 增加懒初始化

新增 `EnsureInitialized()`：

- 当 `Open()` 或 `GetPortraitData()` 首次被调用时
- 若 `_portraitMap` 还没建立，则即时根据 `_portraitDatas` 重建字典

这样即使 `DialogueCanvas` 初始是 inactive，也不会因为生命周期尚未完整跑到而空引用。

### 2. 增加安全事件订阅

将原本依赖 `Start()` 的对话 token 订阅改为：

- `OnEnable()` 自动尝试订阅
- `Open()` 里也主动 `EnsureSubscribed()`
- `OnDisable()` / `OnDestroy()` 安全取消订阅

这样可以避免 UI 初始隐藏时遗漏订阅，减少首次打开时丢 token 的风险。

### 3. 增加缺失配置日志

当 `npc_id` 在 `_portraitDatas` 中找不到对应立绘配置时，输出 warning：

- `[PortraitDialogueUI] 未找到 npc_id=xxx 的立绘配置`

便于区分“生命周期未初始化”和“资源没配全”两类问题。

## 验证结果

- [x] `PortraitDialogueUI.GetPortraitData()` 不再直接依赖 `Awake()` 先执行
- [x] `DialogueCanvas` 当前处于 inactive 也可安全调用 `Open()`
- [x] 当前未发现本次改动引入的新编译错误

## 说明

通过场景对象检查可确认：

- `DialogueCanvas` 当前 `active = false`
- `PortraitDialogueUI` 的 `_portraitDatas`、`_bgImage`、`_portraitImage` 等序列化引用都还在

因此本次问题属于“隐藏 UI 被外部直接调用时，内部运行时字典尚未初始化”的生命周期问题，而不是资源引用整体丢失。
