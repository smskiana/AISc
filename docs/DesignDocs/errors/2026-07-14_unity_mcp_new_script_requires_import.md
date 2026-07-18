# Unity MCP 外部新增脚本需要显式导入

## 错误现象

通过文件系统新增 C# 脚本后调用 `refresh_unity`，Unity Console 没有编译错误，但脚本没有生成 `.meta`，`manage_components` 报告找不到组件类型。

## 根本原因

本次 Unity MCP 会话的普通脚本刷新没有稳定识别外部新文件。已有脚本修改可以编译，但全新的脚本资产尚未进入 Unity AssetDatabase，因此项目程序集和组件类型查询都不可见。

## 正确做法

1. 外部新建 C# 文件后，先对每个新脚本调用 Unity MCP `manage_asset(action=\"import\")`。
2. 确认返回 `UnityEditor.MonoScript`、GUID 和 instance ID，并检查对应 `.meta` 已生成。
3. 再调用 `refresh_unity` 请求编译并等待 Editor ready。
4. Console 无错误后，才使用 `manage_components` 挂载新类型。

## 适用范围

通过 `apply_patch` 或其他编辑器外方式新增 Unity C#、Shader、配置资产后，需要立即在当前 Unity MCP 会话中挂载或查询该资产的场景修改。
