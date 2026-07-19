# 樱桥通 (SakurabashiDoori) — AI社区模拟游戏

## 项目概览
- **类型**: PC单机, 二次元治愈日常向
- **舞台**: 商店街「樱桥通」— 200m老街
- **玩家**: 受够996回老家, 继承奶奶的喫茶店
- **NPC**: 5人 (花店/面包店/旧书店/和果子店/派出所)
- **技术**: Unity (前端) + Python FastAPI (后端) + Claude API (LLM) + LanceDB (向量)

## 架构
```
Unity ←── WebSocket(localhost:8765) ──→ Python FastAPI
      ←── REST(localhost:8766) ──→

Python负责: 记忆图管理 / LLM路由检索 / NPC行为决策 / Prompt组装
Unity负责:   场景渲染 / 动画 / UI / 导航 / 输入
```

## 核心设计文档
- `docs/DesignDocs/MemoryArchitecture.md` — 主设计文档 (v0.5 图记忆模型 + 2026-07-11 v0.7 当前实现口径)
- `docs/DesignDocs/HANDOFF.md` — 交接文档 (DB Schema, WebSocket协议, 实现顺序)
- `docs/DesignDocs/memory/graph-memory-model.md` — 图记忆模型独立规格
- `docs/DesignDocs/memory/graph-demo-sakura.md` — 鹿岛樱记忆图可视化演示
- `docs/DesignDocs/CharacterPresets.md` — 角色预设 (已选Preset C)
- `docs/DesignDocs/MapDesign.md` — 地图设计

## 关键设计决策 (v0.5 设计 / v0.7 当前口径)
1. **轻量联想图**: 每个NPC独立维护图；当前图是联想索引层，SQLite 存节点ID与双向 clarity 边，向量层存节点内容
2. **多跳图路由**: 白天以图路由为主、向量少量兜底；当前分 `player_dialogue` / `npc_dialogue` / `nightly_impression` 三种模式
3. **当前遗忘机制**: 近期优先用边 clarity 衰减 + archived 归档；四阶段退化保留为远期设计，不作为当前必须追齐项
4. **午夜强制睡眠**: 所有重LLM调用在24:00批量执行, 白天零延迟
5. **检索深浅控制**: 近期用检索模式参数与本地排序表达深浅差异；完整四策略选择器暂缓
6. **双向不对称边权重**: A→B和B→A独立, 触发线索到事件的权重通常更强
7. **印象夜间刷新**: 基准印象由图记忆 + 短期记忆夜间生成并写入 `npc_impressions`，白天互动只做 delta 微调

## 共享配置 (shared/)
- `locations.json` — 9区40+地点
- `actions.json` — 7类30+行为 + 地点-行为关联表
- `items.json` — 10个初始物品

## 编码规范
- Python: 类型提示, async/await, Pydantic模型
- Unity C#: 命名规范与Unity标准一致
- 所有AI行为走固定ID目录, LLM永远不自由生成地点/行为名
- Embedding走本地BGE模型, 不产生API费用

---

# AI 开发规则

## 0. 会话启动必读

**每个新对话开始时，AI 必须按功能读取最小上下文：**

1. **`AGENTS.md`** — 当前项目级开发规则。
2. **`docs/ProjectIndex.md`** — 从任务所属功能域进入对应 Workstream 和代码目录 README。
3. 仅在追溯实现原因时，从 **`docs/AIChanges/ChangeIndex.md`** 进入主要功能目录，按主题读取最相关的 plan / execution / test。
4. handoff 只作归档；除非用户要求接续指定会话，或功能索引和代码无法说明遗留状态，不按日期读取“最新”记录。

## 1. 核心行为底线（必须遵守）

1. **变更策略**: 修 bug、补小功能、做局部修正时，强制最小修改，只改明确范围，避免把原问题修坏；新系统设计、结构治理和用户已明确同意的大改，不为了“少改”继续沿用失衡结构。
2. **协作编辑**: 编辑前先读最新内容；尊重人工修改，有冲突先询问；优先复用现有符号、函数和结构。
3. **类减重与扩展性（硬约束）**: 当一个类已经明显过重，或本轮改动会继续把多职责、多状态、多分支、多依赖塞进同一个类时，必须先向用户请求“减重”指令，再继续扩张；不能抱着“先凑合，后面再拆”的想法继续堆。若暂不请求减重，也必须提前预留职责边界、扩展位或可替换接口。
4. **Unity MCP优先（硬约束）**: 场景、Prefab、SerializeField 连线、UI 结构、控件摆放、编辑器生成流程等资产层问题，默认必须先用 Unity MCP 在编辑器资产层解决，不能退回运行时代码兜底；详细执行方式、默认约定与例外边界统一见 [docs/DesignDocs/UnityMCPUsageRules.md](/F:/GameProject/unity/AISc/docs/DesignDocs/UnityMCPUsageRules.md:1)。
5. **命名与索引规范**: 项目内命名与文件索引统一遵循 [docs/DesignDocs/ProjectNamingAndIndexing.md](/F:/GameProject/unity/AISc/docs/DesignDocs/ProjectNamingAndIndexing.md:1)；Unity 场景 / Prefab / UI 层级标签同时参考 `docs/DesignDocs/UnityNamingTags.md`。
6. **交付要求**: 始终使用中文；复杂需求先出方案，通过后再实现；完成后输出修改点清单，代码片段必须标注源文件行号。

## 2. 代码注释

1. **绝不修改或删除原有注释**。
2. AI **新增**或**实质性修改**的函数：定义前至少一行功能注释（C# `///` 或 `//`，Python `"""` 或 `#`）。
3. 复杂分支可补简短行内注释。禁止冗长复述代码。
4. 仅为补注释去动未改的旧函数 → 克制，只补函数头注释。

## 3. 执行案、执行记录与测试记录（互相索引）

**每次非平凡修改必须在主要功能目录产生三份互链文档，并由三个独立会话依次完成：**

| 文件 | 命名 | 内容 |
|------|------|------|
| 设计方案 | `YYYY-MM-DD_<主题>_plan.md` | 需求理解、方案思路、涉及文件、风险点 |
| 执行记录 | `YYYY-MM-DD_<主题>_execution.md` | 实际改动、实现期最低门禁、问题和未完成项 |
| 测试记录 | `YYYY-MM-DD_<主题>_test.md` | 独立测试环境、工具选择、证据、结果和未覆盖项 |

**互相索引规则：**
- plan、execution、test 在顶部互相链接。
- execution 只能得出“实现完成，待独立测试”或“实现未完成”；test 通过后才能认定复杂任务整体完成。

**触发时机：**
- 新建文件 ≥2 个，或修改文件 ≥3 个 → 必须依次创建 plan、execution、test
- 单文件几行且无需独立验收的小修 → 可跳过 plan / test，但事后必须创建 execution 并说明例外
- 纯探索/读代码 → 不需要

测试或制定验收方案前，先读取 `docs/Workstreams/TestingAndDiagnostics/README.md`，按风险选择现有工具，再只读取所选工具的叶子 README；不得一次性加载全部工具说明。

## 4. 低级错误预防

当遇到可复用的错误并已更正后：
1. 分析**错误现象、根本原因、正确做法**
2. 为该错误创建独立明细文件，并回写错误索引
3. 后续修改前先回顾错误索引，而不是把细节堆在本文件里

错误索引入口：

- [docs/DesignDocs/ErrorPreventionIndex.md](/F:/GameProject/unity/AISc/docs/DesignDocs/ErrorPreventionIndex.md:1)
