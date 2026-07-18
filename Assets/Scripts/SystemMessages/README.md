# SystemMessages 脚本目录

## 文件夹功能

负责普通提醒、阻塞弹窗和加载遮罩的排队与展示。

## 文件夹内容

- `SystemMessageController`: 管理两类消息队列和加载状态，并通过暂停模块申请来源。
- `SystemMessageView`: 只管理资产化控件的文本、显隐和按钮事件。

普通提醒不暂停；阻塞弹窗和加载遮罩使用不同暂停来源，关闭一个不会释放另一个。

加载遮罩的阶段文字和进度下限由 `SetLoadingProgress` 接收；同一次加载只会提高目标进度，不会重置已显示的视觉值。`SystemMessageView` 用 UI 时间域平滑显示并在成功前限制为 95%，完成时才快速收口到 100%；标题、阶段文字和 Slider 都是 `Town_Main` 既有 Canvas 下的资产化控件，中文字体使用 `Assets/Fonts/MSYH SDF.asset`。
