# 协议与存档底座设计执行记录

> 设计方案: [plan.md](2026-07-14_协议与存档底座设计_plan.md)

## 实际改动

1. 新增 ADR-0006，确定 Unity 权威世界存档、Python 权威记忆检查点。
2. 新增协议与存档详细设计，定义状态所有权、envelope、可靠性等级、检查点事务、重连和兼容迁移。
3. 新增 `ProtocolAndSave` Workstream，承接七批实施状态。
4. 回写 ProjectIndex、Workstreams、Roadmap、FrontendArchitecture 和协议执行证据入口。

## 当前结论

1. 两端不建设统一数据库。
2. `checkpoint_id` 是两端逻辑存档一致性的关联键。
3. Unity 主导保存 / 加载；Python 只提交记忆检查点。
4. Python 现有世界状态表不立即删除，进入兼容迁移期。
5. 临时对话、移动、LLM 流、UI 和连接状态不进长期存档。

## 验证

1. ADR、详细设计、Workstream 和执行证据已互相建立入口。
2. 本批只修改文档，未触碰 Unity 资产或运行行为。

## 未完成项

后续依次执行协议公共层、Python 记忆检查点、Unity 主存档、双端事务、重连快照和旧世界状态迁移。
