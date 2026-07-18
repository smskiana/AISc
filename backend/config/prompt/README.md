# Prompt 数据层

这里保存 Prompt 任务规格、必要系统契约、响应契约和标签渲染约定。业务模块只传结构化上下文；不要把角色、地点或行为大段文案重新写回业务代码。

`player_reply_suggestions` 的业务主体规则属于 `system_contracts.yaml`：玩家是唯一发言者、当前 NPC 是接收者；NPC profile、关系、语气和现场感知只作背景。`response_contracts.yaml` 只保留机器 JSON 格式，不能承载该主体规则。
