# AIChanges 目录说明

## 文件夹功能

本目录保存项目实际实现修改的方案、执行记录、测试证据和历史交接。它是证据库，不是当前工程口径的第一入口。

## 文件夹内容

- `ChangeIndex.md`: 功能目录总路由。
- 按 `ChangeIndex.md` 路由的功能目录：保存对应系统的 plan / execution / test。
- `Archive/Handoffs/`: 保存历史会话交接。
- `artifacts/`: 保存日志、数据库、摘要和隔离产物。

## 使用方式

先从 `ChangeIndex.md` 选择功能目录，再用主题关键词搜索。不得根据“最新日期”推断当前口径；当前状态应先看对应 Workstream、ADR 和代码。

## 放置规则

1. 新记录按主要变更目标进入一个功能目录。
2. plan / execution / test 文件名保留 `YYYY-MM-DD_<主题>_<类型>.md` 作为审计信息。
3. 纯讨论、排期和未来任务不创建执行记录，直接更新 Roadmap、Workstream 或设计文档。
4. 根目录只保留 `README.md` 和 `ChangeIndex.md`。
5. test 与同主题 plan / execution 放在主要功能目录；跨系统纯跑测或诊断任务才进入 `TestingAndDiagnostics/`。
