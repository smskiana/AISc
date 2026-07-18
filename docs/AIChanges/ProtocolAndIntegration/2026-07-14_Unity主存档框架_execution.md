# Unity 主存档框架执行记录

> 设计方案: [plan.md](2026-07-14_Unity主存档框架_plan.md)

## 实际改动

1. 新增 Unity 世界存档 DTO、manifest 和稳定状态边界。
2. 新增临时目录、SHA-256、原子替换与回滚仓储。
3. 新增基于接口注册的 schema migration 链。
4. 新增独立 `SaveCoordinator`，不把事务状态放入 `GameManager`。

## 验证

Unity MCP 刷新和编译通过，Console 0 error。
