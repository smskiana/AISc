# 重复字段名导致补丁命中错误类型

## 现象

为 `ScheduleOwnerDiagnosticSnapshot` 增加 `failure_detail` 时，只以重复出现的 `failure_reason` 作为补丁上下文，字段被插入前一个 `NpcDailyScheduleReadyMsg`，直到 Unity 测试编译才发现目标 DTO 缺字段。

## 根本原因

局部补丁上下文没有包含目标类名或足够唯一的相邻字段，重复符号使补丁语法正确但语义位置错误。

## 正确做法

1. 修改含重复字段名的长 DTO 文件时，补丁上下文必须包含目标类声明或两侧唯一字段。
2. 补丁后立即用 `rg` 同时检查类名和新增符号位置。
3. 在进入 Play Mode 前先通过 Unity 编译/定向测试门禁。

## 影响范围

含多个相似 DTO、重复序列化字段或重复测试夹具的 C#、Python 和配置文件。
