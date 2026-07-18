# 2026-07-17: 稳定投影 ID 路由与 scope 角色越权

## 错误现象

冷启动初始知识接入后出现两类问题：

1. `initial_knowledge__sakura__fact_id` 被 LanceDB 批量刷新逻辑按 `node_id.split("_")` 解析成了错误的 NPC 分组。
2. `participants` 事实的 subject 观察者仅因出现在 `subject_ids` 就被纳入投影，绕过了参与者权限范围。

## 根本原因

1. 稳定节点 ID 是审计主键，不应同时承担可逆编码 owner 的职责；双下划线和未来 ID 扩展都会让字符串拆分不可靠。
2. 角色匹配优先级不能替代 knowledge scope 约束。必须先由 scope 限定可用角色，再在该 scope 内选择 subject / participant / explicit knower 等最强依据。

## 正确做法

1. 写入批次携带显式 `npc_id` 元数据；旧 `node_{npc_id}_{random}` 节点只保留兼容 fallback。
2. visibility decision 先按五种 scope 分派，再应用事实级排除和角色规则；`private` 才允许 subject 角色，`participants` 只允许 participant 角色。
3. 为稳定 ID、每种 scope、主体/参与者模板和实际冷启动图写入分别保留单测与集成测试。

## 适用范围

稳定节点 ID、LanceDB/SQLite 批量写入分组、知识权限投影、观察者视角记忆和诊断快照。
