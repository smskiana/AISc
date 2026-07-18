# API 模块

## 文件夹功能

提供后端 HTTP、WebSocket 和消息协议入口。

## 文件夹内容

包含连接生命周期、客户端命令解析、事件发送和接口路由。业务编排应下沉到 `application/` 或对应领域模块。

协议 envelope、session 和 sequence 查看 `backend/src/protocol/README.md`；NPC-NPC 社交状态机查看 `backend/src/npc/social_session.py`，不要在 API 入口重新实现等待逻辑。

`GET /api/npc/{npc_id}/initial_knowledge_projection_snapshot` 是冷启动知识的只读诊断入口，支持 `source_fact_id` 和 `include_excluded`；权限判断与事实模板由 Memory 模块提供，API 只负责传输。
