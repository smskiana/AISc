> 执行记录：[2026-07-22_IDE_MCP项目认知图工具_execution.md](../ProjectCognition/2026-07-22_IDE_MCP项目认知图工具_execution.md)
>
> 测试记录（后续独立测试会话创建）：[2026-07-22_IDE_MCP项目认知图工具_test.md](../ProjectCognition/2026-07-22_IDE_MCP项目认知图工具_test.md)

# IDE + MCP 项目认知图工具执行案

## 1. 需求理解

本工具面向 AI 辅助开发场景，帮助第一次进入或暂时不熟悉某段代码的开发人员快速回答以下问题：

1. 当前功能由哪些功能域、子功能和类组成。
2. 每个类的主要职责是什么。
3. 类之间存在什么主要业务关系。
4. 一条主要关系由哪些具体方法调用、继承、接口实现、引用、事件或协议证据支持。
5. 相关代码位于哪里，如何从认知图跳转到 IDE 中的真实符号。

工具第一阶段只服务当前 AISc 仓库，使用现有 codebase-memory 知识图谱作为主要代码事实来源；后续分阶段扩展为不依赖 Unity、C# 或 Python 的通用项目认知工具。最终形态是“薄 IDE 适配器 + 独立项目认知 MCP Server + 可替换代码分析适配器”，不能把解析、范围控制和认知存储全部锁死在某个 IDE 插件中。

本工具只负责快速理解，不承担架构审查、代码修改、持续后台监控、自动全仓更新或运行时业务诊断。

## 2. 已确认产品口径

1. 支持范围分阶段从当前仓库扩展到任意项目，不局限 Unity、C# 或 Python。
2. 产品入口采用 IDE 与 MCP 结合的形态。
3. AI 可以根据目录、命名、文档、调用密度和图聚类提出多层功能划分。
4. 同一个类允许出现在多个功能视图中，但只有一个主要归属；其他位置使用次级归属或引用，不复制类实体。
5. 更新由人员主动触发，不因打开 IDE、代码变化或定时任务自动更新认知。
6. 默认执行分功能域、按需、增量认知更新；不得因发现跨域调用而跳出已有功能域。
7. 初次遇到陌生区域时，只分析用户提及的功能、符号及理解它所必需的最小证据，不扫描完整陌生目录。
8. 只有用户明确要求“全面更新”并确认范围与预算后，才允许更新整个项目。
9. 第一阶段认知数据保存在本地，不要求提交 Git，也不建设团队协作和权限系统。

## 3. 所属功能与既有口径

- 主要功能域：项目治理。
- 关联功能域：测试与诊断。
- Workstream：`docs/Workstreams/ProjectGovernance/README.md`。
- Roadmap：新增项目开发认知工具，不改变现有游戏功能路线；实施后需在 Roadmap 增加独立治理工具条目，不能混入 Unity 前端或记忆系统任务。
- 相关 ADR：ADR-0004、ADR-0005。现有 ADR 只约束项目文档索引，不足以决定新工具的长期存储和跨 IDE 边界；第一阶段验证不新增 ADR，通用化前再判断是否达到 ADR 条件。
- 命名与索引：`docs/DesignDocs/ProjectNamingAndIndexing.md`。
- 测试发现入口：`docs/Workstreams/TestingAndDiagnostics/README.md`。
- 代码事实基础：当前 codebase-memory 索引已包含 Class、Method、File、CALLS、USAGE、INHERITS、IMPLEMENTS 等节点或边，可用于第一阶段验证。
- Unity MCP：第一阶段不修改场景、Prefab、SerializeField 或 UI 资产，不适用 Unity MCP 资产层规则；如果后续选择 Unity Editor 作为 IDE 适配器，必须另开方案并先读取 Unity MCP 规则。

## 4. 统一领域语言

以下术语是实现、MCP interface、IDE 文案和测试共同使用的正式名称：

| 术语 | 定义 | 不表示 |
|------|------|--------|
| 项目认知 | 对功能域、代码符号、主要职责和语义关系的可追溯快照 | 原始源码副本或完整架构真相 |
| 功能域 | 开发人员用于理解项目的一层业务或技术功能边界，可包含子功能域 | 代码目录或类 |
| 代码符号 | 由分析器发现的类、接口、方法、函数等稳定定位对象 | 功能域节点 |
| 功能归属 | 代码符号在某个功能域中的主要、次级或引用关系 | 复制代码符号 |
| 事实关系 | 由代码分析器提供的调用、继承、实现、引用、事件或协议等证据 | AI 总结 |
| 主要关系 | AI 或开发人员将多条事实关系聚合后形成的可读语义关系 | 单一方法调用的别名 |
| 请求范围 | 用户明确提出的功能域、功能、文件或符号范围 | AI 自动扩大的范围 |
| 解析范围 | 系统从请求范围确定的本次目标符号集合 | 允许修改的最终集合 |
| 证据范围 | 为理解目标允许只读访问的外围符号和关系，可有限跨域 | 域外认知修改权限 |
| 可变更范围 | 本次事务真正允许修改的认知节点和关系集合 | 所有已读取内容 |
| 陌生探索域 | 尚无正式功能域时围绕用户提及内容建立的临时范围 | 自动创建的正式功能域 |
| 局部认知更新 | 在签发范围内更新事实和语义的显式事务 | 运行时代码热更新 |
| 全项目更新 | 经独立明确授权后覆盖整个项目的认知更新 | 普通局部更新的自动升级 |

正式文案使用“局部认知更新”或“分区增量更新”，避免使用容易与运行时代码混淆的“热更”。

## 5. 核心不变量

### 5.1 范围不变量

每次更新必须同时形成四个不可混用的集合：

```text
RequestedScope：用户明确提出的范围
ResolvedScope：确定性解析器解析出的目标符号
EvidenceScope：为理解目标允许只读的外围证据
MutationScope：本次允许写入的认知节点和关系
```

必须满足：

```text
MutationScope ⊆ ResolvedScope
ResolvedScope 不得越过 RequestedScope 对应的已确认功能域边界
EvidenceScope 可以受限跨域，但域外部分只能读取
```

### 5.2 功能域不变量

1. 已确认功能域的稳定 ID、名称和父级默认锁定。
2. 普通局部更新不能移动、重命名、合并或删除已确认功能域。
3. AI 只能提出新子域、归属调整和重组建议，不能直接应用。
4. 人工确认的功能归属不能被后续 AI 更新覆盖。
5. 新发现但无法归属的符号进入“待归类”或陌生探索域。
6. 局部更新不得重跑全局聚类并据此重排既有功能树。

### 5.3 跨域不变量

1. 域内关系可以更新事实、摘要和证据。
2. 跨域关系只更新当前域拥有的描述，并保存指向域外稳定符号的引用。
3. 域外功能域、类摘要和归属不能被当前事务修改。
4. 域外证据变化只标记 `external_evidence_changed`，等待用户主动更新对应功能域。
5. 发现跨域调用不能自动扩大 `MutationScope`。

### 5.4 更新不变量

1. 更新只能由用户主动触发。
2. 普通更新不能自动升级为全项目更新。
3. 全项目更新使用独立命令、独立权限和二次确认，不复用普通更新入口。
4. AI 负责提出候选范围和语义，确定性范围引擎负责裁剪并签发范围。
5. 后续 MCP 写操作必须携带签发的 `scope_id` 和范围哈希，不能追加新符号。
6. 预览与应用分离；未经用户确认的 AI 建议不写入正式认知。
7. 应用时再次检查基础快照和范围，任一越界导致整次事务拒绝。

## 6. 目标架构与模块边界

```text
IDE Adapter
  -> Project Cognition MCP Server
       -> Scope Resolution Module
       -> Cognition Update Module
       -> Cognition Query Module
       -> Snapshot Store Adapter
       -> AI Semantics Adapter
       -> Code Graph Adapter
            -> 第一阶段：codebase-memory
            -> 后续：LSP / Tree-sitter / 语言专用索引器
```

### 6.1 IDE Adapter

职责：

1. 提供功能域树、类关系视图、关系证据展开、差异预览和代码跳转。
2. 提交当前文件、选中符号、光标位置和用户输入作为范围解析上下文。
3. 展示当前认知所基于的代码 revision 和是否可能过期。
4. 不自行决定更新范围，不持有领域规则，不直接写认知存储。

第一阶段不在本 plan 中锁定 VS Code、Rider 或 Visual Studio。先完成 MCP 核心和最小测试客户端；IDE 选择需要在执行前由用户确认，否则执行会话只允许完成 MCP 核心，不得擅自创建 IDE 插件。

### 6.2 Scope Resolution Module

这是范围安全的唯一权威模块，对外保持少量深 interface：

```text
resolve_update_scope(request, ide_context, budget) -> ScopeResolution
validate_scope(scope_id, base_snapshot) -> ScopeValidation
```

模块内部负责：

1. 解析用户明确提及的功能域、文件和符号。
2. 将自然语言候选映射到确定性代码符号。
3. 应用功能域锁、跨域规则、深度和数量预算。
4. 生成四层范围、排除项、警告、范围哈希和短期有效的 `scope_id`。
5. 对陌生区域建立临时探索域，不直接写入正式功能树。

调用方不得分别调用“找种子、扩一跳、裁预算、检查边界”等浅接口并自行编排。

### 6.3 Cognition Update Module

对外 interface：

```text
preview_scoped_update(scope_id, base_snapshot) -> UpdatePreview
apply_scoped_update(scope_id, preview_id, accepted_change_ids) -> ApplyResult
request_full_update(project_id, explicit_confirmation, budget) -> FullUpdateScope
```

模块负责事实差异、AI 语义建议、越界检测、并发快照检查和原子提交。`request_full_update` 与普通更新保持独立入口，且确认内容必须包含目标项目、预计文件数、符号数和模型预算。

### 6.4 Cognition Query Module

对外 interface：

```text
get_domain_overview(domain_id, depth)
find_symbol(query, domain_id?)
get_symbol_context(symbol_id)
get_primary_relations(node_id)
expand_relation_evidence(relation_id, limit)
check_scope_freshness(domain_id | symbol_id)
```

查询 interface 不暴露内部数据库表、图查询语言或 codebase-memory 专属节点结构。

### 6.5 Code Graph Adapter

统一语言无关输入模型，至少提供：

```text
resolve_symbols(query, path_hint?)
get_symbol(symbol_id)
get_direct_relations(symbol_ids, relation_types, depth=1)
get_revision()
```

第一阶段适配 codebase-memory 的 Class、Interface、Method、Function、File 以及 CALLS、USAGE、INHERITS、IMPLEMENTS 等事实。不能假定“一类一文件”；符号身份由仓库身份、语言、文件路径、qualified name 和分析器 identity 共同确定。

codebase-memory 的具体接入方式必须在执行会话先做可行性探针：优先通过受支持的 MCP client 或稳定接口读取，不直接依赖其私有数据库 schema。若无法从新 MCP Server 稳定调用现有图谱，执行会话应停止在适配器探针，不得改为复制私有图数据库实现。

### 6.6 AI Semantics Adapter

只接收签发范围内的结构化摘要，负责：

1. 生成类或功能节点的主要职责建议。
2. 将多条事实关系聚合成主要关系建议。
3. 为陌生探索域提出有限层级的功能划分。
4. 为建议附带事实证据 ID、生成来源和模型信息。

AI 不能签发范围、修改锁定节点、伪造证据 ID 或直接提交快照。第一阶段不依赖 AI 自报 confidence 决定是否自动采用；所有新语义默认是 `proposed`。

### 6.7 Snapshot Store Adapter

第一阶段使用项目本地、非 Git 共享的持久化存储。具体使用 SQLite 或等价嵌入式存储由执行会话根据运行环境确定，但必须通过 adapter 隔离，不能让 MCP interface 暴露存储 schema。

存储必须支持：

1. 当前正式认知快照。
2. 更新预览和短期 `scope_id`。
3. 上一版本回滚点。
4. 代码 revision、分析器版本和 AI 模型信息。
5. 人工与 AI 来源、确认状态和过期状态。
6. 原子应用和基础快照并发检查。

## 7. 核心数据模型

### 7.1 ProjectSnapshot

```text
id
project_id
code_revision
analyzer_revision
schema_version
created_at
parent_snapshot_id
```

### 7.2 CodeSymbol

```text
id
project_id
repository_identity
language
symbol_kind
file_path
qualified_name
analyzer_identity
location
content_fingerprint
status
```

类移动或重命名后的身份匹配必须保守处理。不能只用文件路径，也不能只用简单类名；无法可靠匹配时创建“可能重命名”建议，由用户确认，不自动继承人工描述。

### 7.3 FunctionalDomain

```text
id
project_id
name
summary
parent_id
status: proposed | confirmed | locked | deprecated
source: ai | manual
boundary_policy_id
last_reviewed_revision
```

功能树视觉上按父子层级展示。第一阶段每个正式功能域只有一个父级；符号通过独立 Membership 支持多视图，避免一开始把功能域本身扩成难以约束的多父 DAG。若后续确需多父功能域，应另行设计迁移。

### 7.4 Membership

```text
id
domain_id
symbol_id
role
membership_type: primary | secondary | reference
status: proposed | confirmed | stale
source: ai | manual
locked
```

每个代码符号最多一个 `primary`，可以有多个 `secondary` 或 `reference`。

### 7.5 FactRelation

```text
id
source_symbol_id
target_symbol_id
relation_type
source_location
analyzer_source
revision
```

关系类型第一阶段至少支持调用、继承、接口实现和引用；事件、依赖注入、协议和运行时关系在事实来源能够稳定提供后再增加，不用字符串标签假装已解析。

### 7.6 SemanticRelation

```text
id
source_node_id
target_node_id
title
summary
relation_kind
scope_kind: within_domain | cross_domain
importance
evidence_ids
status: proposed | confirmed | stale | conflicted
source: ai | manual
last_verified_revision
```

`importance` 用于展示排序，不代表事实正确率。主要关系必须至少引用一条当前有效事实证据；纯人工概念关系若没有代码证据，必须明确标记为 `manual_concept`，不能伪装成调用关系。

### 7.7 BoundaryPolicy

```text
domain_id
mutation_policy: inside_only
external_evidence_depth
allow_new_child_domains: propose_only | deny
allow_new_members: propose_only | deny
allow_member_move
allow_domain_rename
max_files_per_update
max_symbols_per_update
max_relations_per_update
excluded_paths
```

### 7.8 ScopeResolution

```text
scope_id
project_id
requested_scope
resolved_scope
evidence_scope
mutation_scope
excluded_items
warnings
budget
base_snapshot_id
scope_hash
expires_at
```

## 8. 范围解析协议

### 8.1 Resolve

输入包含用户原始请求、可选明确功能域、IDE 当前上下文、更新模式和预算。解析优先级为：

1. 用户明确指定的功能域和符号。
2. 用户文字中可确定映射的功能或代码实体。
3. IDE 选中符号和当前文件。
4. 已确认功能归属。
5. 受预算限制的一跳必要证据。

自然语言 AI 只产生候选种子；最终 `ResolvedScope` 必须由代码图事实和边界规则确定。

默认预算建议从保守值起步，并允许项目配置覆盖：

```text
evidence_depth = 1
max_files = 20
max_symbols = 30
max_relations = 100
```

超出预算时返回裁剪结果和扩展建议，不自动提高限制。

### 8.2 Preview

`preview_scoped_update` 只能使用有效 `scope_id`，输出：

1. 事实新增、删除和变化。
2. 类职责与主要关系的 AI 建议。
3. 失效关系。
4. 功能归属和子域建议。
5. 跨域边界事件。
6. 排除项与范围违规。
7. 预计写入数量和 AI 消耗摘要。

存在任何未解决的范围违规时，预览不可应用。

### 8.3 Apply

`apply_scoped_update` 必须携带 `scope_id`、`preview_id`、用户接受的 change IDs 和期望基础快照。服务端重新验证范围哈希、快照版本、锁定状态和全部 change ID；通过后原子生成新快照，失败则不写入任何正式认知。

### 8.4 陌生探索域

当用户提及的代码没有正式功能归属时：

1. 仅以用户提及的功能、文件或符号为种子。
2. 只读取预算允许的一跳必要证据。
3. 创建短期 `ExplorationScope`，不创建正式功能域。
4. AI 可以建议有限的功能层级，默认不超过三层。
5. 用户确认后才将建议提升为正式 FunctionalDomain 和 Membership。
6. 未确认探索结果可丢弃，不污染正式认知。

### 8.5 全项目更新

全项目更新必须满足全部条件：

1. 用户使用明确语义要求全面更新，不能由 AI 根据“更新一下”推断。
2. 工具先展示项目、文件数、符号数、预计时间和模型预算。
3. 用户二次确认后生成短期 full-update authorization。
4. 全项目仍使用 preview/apply，不直接覆盖人工确认内容。
5. 任何确认超时、项目 revision 变化或预算变化都会使授权失效。

## 9. MCP Server Interface

第一阶段建议暴露以下最小工具集：

### 9.1 查询工具

```text
get_domain_overview
find_symbol
get_symbol_context
get_primary_relations
expand_relation_evidence
check_scope_freshness
```

### 9.2 更新工具

```text
resolve_update_scope
preview_scoped_update
apply_scoped_update
request_full_update
```

### 9.3 人工治理工具

```text
confirm_domain_structure
set_symbol_membership
update_manual_summary
reject_proposal
```

所有写工具返回结构化结果和稳定错误码，至少区分：无效范围、范围过期、快照冲突、边界越权、预算超限、证据不存在、锁定内容冲突和适配器不可用。不得要求 AI 通过解析自由文本错误来判断是否写入成功。

资源 URI 可按以下形式提供只读认知：

```text
project-cognition://projects/{project_id}/domains
project-cognition://projects/{project_id}/domains/{domain_id}
project-cognition://projects/{project_id}/symbols/{symbol_id}
project-cognition://projects/{project_id}/relations/{relation_id}
project-cognition://projects/{project_id}/snapshots/current
```

## 10. IDE 交互范围

第一阶段 IDE 体验只要求：

1. 左侧功能域树，支持多层展开到类。
2. 中央视图显示选中功能域或类的主要关系，不默认绘制全项目关系网。
3. 点击关系展开具体事实证据，并能跳转文件与行号。
4. 显示 AI 建议、人工确认、过期和冲突状态。
5. 从当前符号、当前文件、当前功能域发起局部认知更新。
6. 在应用前显示范围、排除域、跨域只读证据和认知差异。
7. 全面更新作为独立、低频命令，不放在普通刷新按钮的直接路径上。

关系图默认限制可见节点和边，优先展示 importance 较高的主要关系；继续展开由用户点击触发，不能一次渲染整个项目。

## 11. 分阶段实施

### 阶段 A：当前仓库 MCP 核心验证

目标：证明受控范围、codebase-memory 事实接入、认知存储和主要关系展开闭环可行。

1. 建立领域模型、范围引擎、快照存储和 MCP Server 骨架。
2. 完成 codebase-memory Code Graph Adapter 可行性探针。
3. 只覆盖当前 AISc 仓库及 C# / Python 已索引事实。
4. 实现查询、resolve、preview、apply 和显式 full-update authorization。
5. 使用最小测试客户端验证，不先绑定具体 IDE。
6. 使用确定性假 AI adapter 或固定 fixture 验证边界；真实 AI 接入放在范围安全成立之后。

阶段门禁：任何测试均不能通过局部更新修改域外认知；若 codebase-memory 无稳定接入 seam，本阶段停止并回到方案会话调整 adapter 边界。

### 阶段 B：AI 语义与陌生探索域

1. 接入 AI Semantics Adapter。
2. 实现类职责、主要关系聚合和有限功能分层建议。
3. 实现证据 ID 白名单验证，拒绝模型生成的未知证据。
4. 实现 proposed/confirmed/manual/stale/conflicted 状态流转。
5. 验证人工确认内容不会被更新覆盖。

阶段门禁：AI 输出不可信或越界时只产生可拒绝建议，不影响正式快照。

### 阶段 C：首个 IDE Adapter

执行前由用户明确选择 VS Code、Rider/JetBrains 或 Visual Studio。IDE adapter 只使用 MCP interface，不直接访问存储或 codebase-memory。

1. 实现功能树、局部关系图、证据展开和源码跳转。
2. 实现范围预览与差异确认。
3. 验证大图按需展开和渲染预算。
4. 保持 MCP Server 可由 AI 客户端独立调用。

### 阶段 D：通用语言与多 IDE

1. 固定语言无关 Code Graph Adapter contract。
2. 增加 LSP、Tree-sitter 或语言专用 analyzer adapter。
3. 支持多仓库和 monorepo identity。
4. 增加第二个 IDE adapter，验证核心没有绑定首个 IDE。
5. 再评估 Git 共享、团队协作、权限和稳定 ADR。

阶段 D 不属于第一轮实现范围，必须基于阶段 A-C 的证据另开 plan。

## 12. 第一轮计划文件边界

以下是阶段 A/B 的建议目标结构，具体语言和依赖在执行会话完成 codebase-memory 接入探针后冻结：

```text
tools/project_cognition/
  README.md
  pyproject.toml 或等价独立包清单
  src/project_cognition/
    domain/
    scope/
    update/
    query/
    mcp/
    adapters/code_graph/
    adapters/ai_semantics/
    adapters/snapshot_store/
  tests/
docs/Workstreams/ProjectCognition/README.md
docs/AIChanges/ProjectCognition/README.md
```

执行会话应先建立实际功能目录和 README，再回写：

1. `docs/ProjectIndex.md`。
2. `docs/Roadmap.md`。
3. `docs/AIChanges/ChangeIndex.md`。
4. `docs/Workstreams/ProjectGovernance/README.md`，将项目认知工具路由到新 Workstream。
5. `docs/AIChanges/ProjectGovernance/` 中本 plan 的 execution 链接。

本 plan 保存在 ProjectGovernance 是因为方案产生时尚无 ProjectCognition 功能目录。执行后续证据应迁移还是继续保留，由执行会话按“不移动既有证据、通过新目录 README 引用本 plan”的最小迁移原则处理，默认不移动本文件。

## 13. 测试工具选择与最低门禁

已先读取 `docs/Workstreams/TestingAndDiagnostics/README.md`。本工具不修改现有 Unity 运行时或后端业务，因此第一阶段不选择 Unity PlayMode、`aisc_debug`、`aisc_control` 或现有游戏后端长跑工具。

执行会话需要为新独立工具建立自身测试入口并注册索引，最低门禁包括：

1. 领域模型 schema 校验和序列化往返测试。
2. Scope Resolution 纯逻辑测试，覆盖域内、跨域、陌生域、预算裁剪和显式全面更新。
3. Snapshot Store 原子应用、冲突、回滚和锁定内容测试。
4. MCP contract 测试，覆盖稳定错误码和无效 `scope_id`。
5. Code Graph Adapter contract test，使用固定小图 fixture，避免测试依赖当前全仓索引状态。
6. codebase-memory 真实只读 smoke，证明能定位当前仓库的已知类和一跳调用关系。
7. AI adapter 使用固定输出测试证据白名单、越界拒绝和人工内容保护；真实模型质量评估与确定性 contract test 分开。
8. 性能基准记录局部更新的文件数、符号数、关系数、范围解析时间、模型输入量和存储写入量。
9. 若阶段 C 实现 IDE adapter，增加 IDE 扩展宿主集成测试和桌面截图验证，检查功能树、关系展开、长名称、窄窗口和大节点数量下无重叠。

实现会话只能得出“实现完成，待独立测试”；独立测试会话读取本 plan、execution 和新工具 README 后创建同主题 `_test.md`。

## 14. 必测场景

1. 更新 `NPC 行为/任务执行`，读取导航接口作为证据，但导航功能域快照字节级不变。
2. 当前类调用三个域外类，只建立三个只读边界引用，不递归展开域外调用。
3. 用户只说“更新这个类”，范围以 IDE 选中符号为种子，不扩大到目录。
4. 用户提到尚无归属的类，只产生 ExplorationScope，不创建正式功能域。
5. AI 建议移动人工锁定类，预览标记冲突且无法应用该 change。
6. AI 返回不属于 EvidenceScope 的证据 ID，整个语义建议被拒绝。
7. Scope 签发后代码 revision 变化，apply 返回范围过期且不写快照。
8. 两个预览基于同一快照，先应用一个后，另一个因基础快照冲突失败。
9. 超过文件或符号预算，系统裁剪并请求扩展授权，不自动提高预算。
10. 普通“更新项目认知”请求不能调用全项目更新；只有明确全面更新并二次确认后得到授权。
11. 一个类具有 primary、secondary 和 reference 归属时，各视图指向同一 CodeSymbol。
12. 类重命名或移动无法可靠匹配时提出候选，不自动继承人工摘要。
13. 删除域内调用后 SemanticRelation 标记 stale；域外关系变化只标记 external evidence changed。
14. 第三方库、测试和生成代码按策略排除，用户显式包含时才进入请求范围。

## 15. 验收标准

### 15.1 阶段 A

1. 能从当前 AISc 索引读取一个已知功能域的类和方法关系，并转换为语言无关模型。
2. 能完成 resolve -> preview -> apply 闭环，正式写入只发生在 MutationScope 内。
3. 已确认功能域和人工归属在局部更新后保持不变。
4. 跨域证据可展开，但域外认知没有任何写入。
5. 陌生区域只围绕用户种子建立 ExplorationScope。
6. 普通更新无法升级为全面更新。
7. 快照支持冲突检测和至少一个上一版本回滚点。
8. 所有 MCP 写工具具有结构化成功结果和稳定错误码。

### 15.2 阶段 B

1. AI 能为类生成简短主要职责，并把多条事实证据聚合成少量主要关系。
2. 每条 AI 主要关系都能展开到当前有效证据，未知证据不能进入快照。
3. AI 能在陌生探索域内提出不超过三层的有限分层，不扫描完整陌生目录。
4. AI 建议默认进入 proposed，人工确认和人工摘要不会被自动覆盖。
5. 相同输入、固定事实和固定 AI fixture 能重现边界判定结果。

### 15.3 阶段 C

1. 开发人员能从 IDE 功能树进入类，查看主要职责和主要关系。
2. 点击关系可以展开方法级证据并跳转到源代码。
3. 发起更新时能清楚看到目标域、包含符号、排除域、跨域只读证据和预计成本。
4. 默认视图不会绘制全项目图；节点和边按需展开且界面不重叠。
5. IDE adapter 移除后，MCP Server 仍能被测试客户端和 AI 客户端独立使用。

## 16. 风险与收口

1. **codebase-memory 接入方式不稳定**：先做 adapter 探针，只依赖其公开 MCP 或稳定 interface；失败则停止实施并更新本 plan，不读取私有存储硬接。
2. **静态调用图不完整**：关系明确标注事实来源；事件、反射、依赖注入和协议关系在没有证据时不伪造完整性。
3. **AI 分层漂移**：已确认域锁定，局部更新不运行全局聚类，AI 只提交 proposed 差异。
4. **范围通过自然语言越权**：AI 只提候选，确定性边界引擎签发哈希范围，apply 再验证。
5. **大型项目性能失控**：默认一跳、硬预算、分层缓存、按需关系展开；全面更新独立授权。
6. **IDE 技术路线过早绑定**：阶段 A/B 使用最小客户端，首个 IDE 必须由用户在阶段 C 前确认。
7. **类与文件身份混淆**：统一 CodeSymbol identity，不采用“一类一文件”作为数据不变量。
8. **新工具污染游戏运行时**：工具使用独立目录、依赖和进程，不向 Unity 或 Python 游戏运行时入口注入开发工具依赖。
9. **认知被误认为权威代码事实**：界面始终展示 revision、来源和状态，主要关系可以展开证据，过期内容显式标记。

## 17. 明确不做

1. 第一轮不支持任意语言、任意仓库和多个 IDE。
2. 不进行后台监听、自动刷新或定时全仓扫描。
3. 不自动修改代码、重构或给出架构合规结论。
4. 不建设团队账号、权限、远程同步和 Git 提交流程。
5. 不以目录结构替代功能域，也不以函数调用替代全部语义关系。
6. 不默认展示全项目关系图。
7. 不把项目认知写入现有游戏记忆系统。
8. 不因当前仓库是 Unity + Python 就把核心模型绑定到这两种语言。

## 18. 执行顺序与会话边界

1. 本会话只创建本执行案，不进入实现。
2. 下一独立执行会话必须明确引用本文件，并以本文件为唯一方案来源。
3. 执行会话先确认首轮是否只做阶段 A/B；若用户同时要求阶段 C，必须先确认目标 IDE。
4. 执行前使用 codebase-memory 重新检查索引；若过期则更新索引并同步 `docs/AIChanges/codebase-memory-mcp_更新.md`。
5. 执行会话先完成 codebase-memory adapter 可行性探针，通过后才能创建完整模块；探针失败不得擅自改用私有数据库。
6. 若实际文件边界、运行时依赖或 codebase-memory interface 与本 plan 不兼容，停止执行并在新的方案会话更新本 plan，不创建第二份 plan。
7. 执行完成后创建同主题 `_execution.md`，只得出“实现完成，待独立测试”或“实现未完成”。
8. 第三个独立测试会话按本 plan 验收标准和 execution 实际变更创建同主题 `_test.md`。
