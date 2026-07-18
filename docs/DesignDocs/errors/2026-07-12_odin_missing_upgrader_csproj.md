# 2026-07-12: OdinUpgrader.cs 缺失但 csproj 仍引用导致编译失败

## 错误现象

安装 Odin 后执行：

```powershell
dotnet build AISc.sln --no-restore
```

失败并报错：

```text
CSC : error CS2001: 未能找到源文件“Assets\Plugins\Sirenix\Odin Inspector\OdinUpgrader.cs”
```

## 根本原因

`Assembly-CSharp-firstpass.csproj` 中仍保留：

```xml
<Compile Include="Assets\Plugins\Sirenix\Odin Inspector\OdinUpgrader.cs" />
```

但当前 Odin 安装目录下实际没有该文件。该问题属于 Unity / 插件安装后的项目文件残留，而不是业务脚本编译错误。

## 正确做法

1. 先确认文件是否真实存在。
2. 如果文件不存在且只是 `.csproj` 残留，移除该 `Compile Include`。
3. 不要在插件目录手动创建空的 `OdinUpgrader.cs` 伪文件。
4. 修复后重新执行 `dotnet build AISc.sln --no-restore`。

## 后续预防

1. 安装或升级 Odin 后，如果命令行编译失败，先检查 `.csproj` 是否引用了不存在的 Sirenix 源文件。
2. Unity 重新生成项目文件后，该问题可能复现；优先让 Unity / Odin 完成导入刷新，再检查残留引用。
