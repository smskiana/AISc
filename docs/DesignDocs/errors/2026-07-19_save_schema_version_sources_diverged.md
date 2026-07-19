# 存档 schema 版本源分叉

## 错误现象

Unity 新建快照已经使用 schema 3，迁移链也包含 2 到 3，但仓储仍只允许写入 schema 2。保存事务先进入 `PreparingUnity`，随后本地 prepare 同步抛出“只能写入当前 Unity 存档 schema”，后续 checkpoint 协调没有启动。

## 根本原因

存档当前版本同时存在于 DTO 默认值、仓储写入/加载目标和迁移链终点。新增 schema 时只更新前两项实现中的一部分，缺少覆盖“默认新档可被当前仓储写入”的回归测试。

## 正确做法

1. 每次提升 Unity 存档 schema 时，同时核对 `GameSaveData.schema_version`、`UnitySaveRepository.CurrentSchemaVersion` 和 `SaveMigrationRegistry` 的最后一个 `ToVersion`。
2. 保留两类聚焦回归：上一版本能迁移到当前版本；默认构造的新快照能通过仓储 prepare 并写出当前版本 manifest。
3. 保存协调器若在进入后续异步阶段前执行本地同步 prepare，诊断时先检查该边界，避免把未发送的 checkpoint 请求误判为网络或 Python 悬挂。

## 适用范围

Unity 主存档 schema、manifest 版本投影、迁移链和双端保存事务。
