# PowerShell Error 自动变量不可覆盖

## 错误现象

文档校验命令把错误预防明细路径赋给 `$error`。PowerShell 变量名不区分大小写，因此该名称等同于内置只读自动变量 `$Error`，赋值触发 `Cannot overwrite variable Error because it is read-only or constant`，并使后续路径扫描收到错误文本而产生次生报错。

## 根本原因

临时校验脚本使用了过于通用的变量名，没有考虑 PowerShell 自动变量不区分大小写。命令又未在开头设置 `$ErrorActionPreference='Stop'`，导致首个赋值错误后仍继续执行，混入无效路径并增加噪声。

## 正确做法

1. 不使用 `$error`、`$input`、`$args`、`$matches`、`$home` 等可能与 PowerShell 自动变量冲突的名字。
2. 路径变量使用职责明确的名称，例如 `$errorDocPath`、`$testRecordPath`。
3. 多步骤校验命令设置 `$ErrorActionPreference='Stop'`，首个基础错误发生时立即停止，不让无效状态传播到后续检查。
4. 校验结果只在命令正常退出后作为门禁证据；部分输出成功不能掩盖同一命令的后续失败。

## 本次修正

模型报告哈希在变量赋值错误前已正确输出，但该次文档路径与空白检查作废。后续改用 `$errorDocPath` 并启用 stop-on-error，重新执行全部文档路径、尾随空白和 Git diff 检查。
