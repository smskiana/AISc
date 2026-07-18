# Dialogue 脚本目录

## 文件夹功能

保存 Unity 侧对话流程和对话状态适配代码。

## 文件夹内容

包括正式对话、快捷回复、加载状态、NPC 世界气泡和 NPC-NPC 社交会合协议。界面布局与控件本体同时查看 `Assets/Scripts/UI/` 和对应 Prefab。

## 当前社交口径

1. `NpcSocialProtocolController` 在 Unity 接受 decision 后原子 reservation，执行会合、内容等待、播放、FAILED / COMPLETE 和本地超时释放。
2. `NpcSocialRendezvousController` 负责距离判断和播放期间移动锁；reservation 不复用 motion lock。
3. `NpcBubbleManager` 只接受当前 session 且 revision 匹配的 `NPC_SOCIAL_CONTENT_RESULT`，最后一句播放结束后回报 COMPLETE。
4. Python 不再发送 `NPC_SOCIAL_PREPARE / NPC_SOCIAL_CANCEL`，也不监督 Unity 会合或播放超时。
