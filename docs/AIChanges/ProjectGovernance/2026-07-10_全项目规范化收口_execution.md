> 设计方案: [2026-07-10_全项目规范化收口_plan.md](2026-07-10_全项目规范化收口_plan.md)

# 全项目规范化收口 — 执行记录

## 完成时间

2026-07-10

## 本次完成内容

本轮已按方案完成第一阶段“规范基线工程”，重点不是大规模历史迁移，而是先把后续协作入口、交接链、检查入口和产物边界固定下来。

本次已完成：

1. 建立项目总索引、设计文档索引、Unity 脚本索引
2. 补新的 `HANDOFF_2026-07-10.md`，让会话感知链不再停留在 `2026-07-08`
3. 更新 `AGENTS.md` 与 `CLAUDE.md` 的会话启动必读，改为优先读取最新 handoff / 最新 execution
4. 新增轻量规范检查脚本，覆盖 shared ID、profile 主键和 Unity 位置配置一致性
5. 为 `docs/AIChanges/` 增加目录说明，并把跑测产物的未来收纳位置收口到 `artifacts/`
6. 更新 7 天跑测脚本的默认产物输出路径，避免继续把隔离数据库和日志堆在 `docs/AIChanges/` 根层

## 实际改动清单

### 新建文件 (8)

| 文件 | 说明 |
|------|------|
| `docs/ProjectIndex.md` | 项目总索引入口 |
| `docs/DesignDocs/Index.md` | 设计文档索引 |
| `Assets/Scripts/Index.md` | Unity 前端脚本索引 |
| `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-10.md` | 最新会话交接文档 |
| `backend/scripts/check_project_conventions.py` | 轻量规范检查脚本 |
| `docs/AIChanges/README.md` | AIChanges 目录边界说明 |
| `docs/AIChanges/artifacts/README.md` | 跑测 / 诊断产物收纳约定 |
| `docs/AIChanges/ProjectGovernance/2026-07-10_全项目规范化收口_execution.md` | 本执行记录 |

### 修改文件 (4)

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | 会话启动必读改为总索引 + 最新 handoff / 最新 execution |
| `CLAUDE.md` | 同步更新会话启动必读 |
| `backend/scripts/run_7day_benchmark.py` | 默认产物输出路径改到 `docs/AIChanges/artifacts/<tag>/` |
| `docs/AIChanges/ProjectGovernance/2026-07-10_全项目规范化收口_plan.md` | 对应本轮方案文档，已按此执行 |

## 关键结果

### 1. 项目终于有稳定索引入口

现在新会话不需要只靠 `AGENTS.md` 和目录硬翻：

- `docs/ProjectIndex.md` 负责总入口
- `docs/DesignDocs/Index.md` 负责设计文档入口
- `Assets/Scripts/Index.md` 负责 Unity 前端主链入口

这样后续无论是继续做前端、后端、设计还是规范治理，都有明确落点。

### 2. 会话交接链已更新到 2026-07-10

此前启动规则仍硬编码到：

- `HANDOFF_2026-07-08.md`
- `2026-07-08_AI自主NPC系统_execution.md`

这已经明显落后于项目当前状态。

本次已：

1. 新增 `HANDOFF_2026-07-10.md`
2. 将两份入口规则改成“优先看最新 handoff / 最新相关 execution”

这能避免后续新会话继续从旧状态起步。

### 3. 规范文档第一次具备了可执行检查入口

新增：

- `backend/scripts/check_project_conventions.py`

当前检查覆盖：

1. `shared/locations.json` 的 zone / spot 命名
2. `shared/actions.json` 的 action id、`location_action_map` 引用
3. `shared/items.json` 的 item id 与 source 合法性
4. `backend/config/npc_profiles/*.json` 的文件名与 `npc_id`
5. `backend/config/location_profiles/*.json` 的文件名与 `location_id`
6. `Assets/Resources/Config/location_positions.json` 与 `shared/locations.json` 的一致性

### 4. `docs/AIChanges/` 产物边界开始收口

本轮没有暴力迁移历史日志和历史产物目录，但已经完成：

1. 写明目录职责
2. 给未来产物指定固定落点
3. 把 `run_7day_benchmark.py` 的默认输出切到：
   - `docs/AIChanges/artifacts/<tag>/`

也就是说：

- 历史混乱先保留
- 新增产物从现在开始按新规则收口

这比一上来全量搬历史文件更稳。

## 验证方式

### 已执行验证

- [x] 读取旧 handoff、最新 execution、设计规范文档与共享配置，确认上下文
- [x] `python backend/scripts/check_project_conventions.py`
  - 返回：`规范检查通过：shared ID、profile 主键、location_positions 一致。`
- [x] `python backend/scripts/run_7day_benchmark.py --help`
  - 确认脚本入口正常、参数可用

### 静态核对

- [x] `AGENTS.md` 与 `CLAUDE.md` 的会话启动规则已同步
- [x] `docs/ProjectIndex.md` / `docs/DesignDocs/Index.md` / `Assets/Scripts/Index.md` 已建立
- [x] `docs/AIChanges/Archive/Handoffs/HANDOFF_2026-07-10.md` 已建立
- [x] `docs/AIChanges/README.md` 与 `docs/AIChanges/artifacts/README.md` 已建立

## 本轮明确没有处理的事项

1. `.git` 仓库异常修复
2. 历史日志与历史跑测产物的全量迁移
3. 历史 GameObject / prefab / JSON 主键的全量重命名
4. 运行时架构层面的进一步大重构

这些都属于高风险或高耦合动作，仍建议单独立项。

## 当前建议的下一个规范治理动作

1. 若继续治理文档层：
   - 给 `docs/AIChanges/` 建立按主题或按日期的更稳定归档策略
2. 若继续治理资产层：
   - 单独做 prefab 内部层级命名收敛
3. 若继续治理工程层：
   - 单独排查 `.git` 为什么失效，再决定是否重建仓库

## 结论

本轮已经把项目从“规则散落、交接链过时、索引缺失、检查缺位”推进到：

- 有总索引
- 有最新 handoff
- 有规则检查脚本
- 有跑测产物边界

这意味着后续再继续做功能开发或局部重构时，已经有一套更稳的协作基线可依赖。
